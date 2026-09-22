"""New-launch ingestion: polls keyless feeds for freshly launched Solana tokens.

Sources (all keyless):
  1. RugCheck /v1/stats/new_tokens  - mints of tokens RugCheck just saw
  2. DexScreener /token-profiles/latest/v1 - newest token profiles (solana only)

New mints are deduplicated and emitted into the intelligence pipeline as
launch items so the bot discovers tokens on its own instead of waiting for
social chatter. The signal engine's safety gate still vets anything it trades.
"""
import asyncio
from collections import deque
from datetime import datetime
from typing import Optional

import httpx
import structlog

from app.core.config import settings
from app.safety.checker import RUGCHECK_NEW_TOKENS_URL


logger = structlog.get_logger()

DEXSCREENER_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"


class LaunchIngestion:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.seen: set[str] = set()
        self.seen_order: deque[str] = deque()
        self.received_count = 0
        self.poll_count = 0
        self.last_poll: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    # ---- lifecycle ----

    async def start(self):
        if not settings.LAUNCHES_ENABLED:
            logger.info("Launch ingestion disabled (LAUNCHES_ENABLED=false)")
            return
        self.running = True
        self._client = httpx.AsyncClient()
        # Seed the seen-set so we only emit genuinely new launches after boot
        await self._poll(seed_only=True)
        self.task = asyncio.create_task(self._poll_loop())
        logger.info("Launch ingestion started", poll_seconds=settings.LAUNCHES_POLL_SECONDS)

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Launch ingestion stopped", received=self.received_count)

    def get_status(self) -> dict:
        return {
            "enabled": settings.LAUNCHES_ENABLED,
            "running": self.running,
            "received_count": self.received_count,
            "poll_count": self.poll_count,
            "tracked_mints": len(self.seen),
            "last_poll": self.last_poll.isoformat() if self.last_poll else None,
            "last_error": self.last_error,
        }

    # ---- polling ----

    async def _poll_loop(self):
        while self.running:
            try:
                await self._poll()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.last_error = str(e)
                logger.warning("Launch poll failed", error=str(e))
            await asyncio.sleep(settings.LAUNCHES_POLL_SECONDS)

    async def _poll(self, seed_only: bool = False):
        if not self._client:
            return
        self.poll_count += 1
        self.last_poll = datetime.now(timezone.utc)
        items: list[dict] = []
        items += await self._fetch_rugcheck_new()
        items += await self._fetch_dexscreener_profiles()

        fresh: list[dict] = []
        for item in items[: settings.LAUNCHES_MAX_PER_POLL]:
            mint = item.get("mint")
            if not mint or mint in self.seen:
                continue
            self._remember(mint)
            fresh.append(item)

        if seed_only:
            logger.info("Launch ingestion seeded", tracked=len(self.seen))
            return

        for item in fresh:
            self.received_count += 1
            await self.pipeline.process(self._to_pipeline_item(item))
        if fresh:
            logger.info("New launches ingested", count=len(fresh))

    def _remember(self, mint: str):
        self.seen.add(mint)
        self.seen_order.append(mint)
        # bound memory: keep the most recent 5000
        while len(self.seen_order) > 5000:
            old = self.seen_order.popleft()
            self.seen.discard(old)

    async def _fetch_rugcheck_new(self) -> list[dict]:
        try:
            r = await self._client.get(
                RUGCHECK_NEW_TOKENS_URL, timeout=20.0,
                headers={"User-Agent": "narrative-sniper/1.0"},
            )
            r.raise_for_status()
            tokens = r.json() or []
        except Exception as e:
            logger.debug("RugCheck new_tokens fetch failed", error=str(e))
            return []
        out = []
        for t in tokens:
            mint = t.get("mint")
            if not mint:
                continue
            out.append({
                "mint": mint,
                "symbol": t.get("symbol") or "",
                "name": t.get("symbol") or mint[:8],
                "creator": t.get("creator") or "",
                "launchpad": t.get("program") or "",
                "detected_at": t.get("createAt") or "",
                "source": "rugcheck",
                "url": f"https://rugcheck.xyz/tokens/{mint}",
            })
        return out

    async def _fetch_dexscreener_profiles(self) -> list[dict]:
        try:
            r = await self._client.get(
                DEXSCREENER_PROFILES_URL, timeout=20.0,
                headers={"User-Agent": "narrative-sniper/1.0"},
            )
            r.raise_for_status()
            profiles = r.json() or []
        except Exception as e:
            logger.debug("DexScreener profiles fetch failed", error=str(e))
            return []
        out = []
        for p in profiles:
            if (p.get("chainId") or "").lower() != "solana":
                continue
            mint = p.get("tokenAddress")
            if not mint:
                continue
            links = p.get("links") or []
            website = next((l.get("url", "") for l in links if l.get("label") == "Website"), "")
            out.append({
                "mint": mint,
                "symbol": "",
                "name": (p.get("description") or "")[:60] or mint[:8],
                "description": p.get("description") or "",
                "website": website,
                "source": "dexscreener",
                "url": p.get("url") or f"https://dexscreener.com/solana/{mint}",
            })
        return out

    # ---- normalization ----

    def _to_pipeline_item(self, launch: dict) -> dict:
        symbol = launch.get("symbol") or ""
        name = launch.get("name") or launch["mint"][:8]
        tag = f"${symbol}" if symbol else name
        text = (
            f"New token launch: {tag} ({name}). "
            f"Mint: {launch['mint']}. Source: {launch.get('source')}. "
            f"{launch.get('description', '')[:200]}"
        ).strip()
        return {
            "text": text,
            "platform": "launches",
            "handle": f"launchpad:{launch.get('source', 'unknown')}",
            "url": launch.get("url", ""),
            "timestamp": datetime.utcnow().isoformat(),
            "engagement": 0,
            "token_mint": launch["mint"],
            "token_symbol": symbol,
            "token_name": name,
            "launch_source": launch.get("source"),
        }
