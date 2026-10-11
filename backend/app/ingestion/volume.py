"""Volume watcher: the sniper's second pair of eyes.

The social pipeline only hears *talk*. A coin can be bought hard in silence —
no posts, no comments — and the narrative engine would never know. This
watcher polls DexScreener stats for the tokens the launch ingestion is
already tracking (the newest launches, where silent pumps live) and raises
a narrative when buying suddenly explodes:

  - buys in the last hour >= VOLUME_MIN_BUYS_H1, and
  - volume in the last hour >= VOLUME_MIN_VOLUME_H1_USD, and
  - that volume is at least VOLUME_SPIKE_MULTIPLE x the previous reading
    (first sightings of an already-hot token count too).

The alert is published through pipeline.emit_narrative, so it lands on the
dashboard and goes through the signal engine's normal gates (price lookup,
safety check, cooldowns) before any paper trade opens. A per-token cooldown
stops one pumping coin from spamming alerts.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import structlog

from app.core.config import settings
from app.models import Narrative, SourceRef
from app.safety.checker import DEXSCREENER_URL


logger = structlog.get_logger()


def is_spike(prev_h1_volume: Optional[float], stats: dict) -> bool:
    """Pure spike test, kept separate so it can be unit-tested without I/O."""
    buys = stats.get("buys_h1") or 0
    volume = stats.get("volume_h1") or 0.0
    if buys < settings.VOLUME_MIN_BUYS_H1:
        return False
    if volume < settings.VOLUME_MIN_VOLUME_H1_USD:
        return False
    if prev_h1_volume is not None and prev_h1_volume > 0:
        if volume < prev_h1_volume * settings.VOLUME_SPIKE_MULTIPLE:
            return False
    return True


def parse_pair_stats(payload) -> Optional[dict]:
    """Reduce a DexScreener /tokens response to the stats we care about.

    Picks the most liquid Solana pair for the token. Returns None when the
    token has no usable pair yet.
    """
    pairs = payload if isinstance(payload, list) else (payload or {}).get("pairs") or []
    pairs = [p for p in pairs if (p.get("chainId") or "").lower() == "solana"]
    if not pairs:
        return None

    def liquidity(p):
        return (p.get("liquidity") or {}).get("usd") or 0

    pair = max(pairs, key=liquidity)
    base = pair.get("baseToken") or {}
    volume = pair.get("volume") or {}
    txns = pair.get("txns") or {}
    h1 = txns.get("h1") or {}
    return {
        "symbol": base.get("symbol") or "",
        "name": base.get("name") or "",
        "price_usd": pair.get("priceUsd"),
        "liquidity_usd": liquidity(pair),
        "volume_h1": float(volume.get("h1") or 0),
        "volume_h24": float(volume.get("h24") or 0),
        "buys_h1": int(h1.get("buys") or 0),
        "sells_h1": int(h1.get("sells") or 0),
        "url": pair.get("url") or "",
    }


class VolumeWatcher:
    def __init__(self, pipeline, launch_ingestion):
        self.pipeline = pipeline
        self.launches = launch_ingestion
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self.last_volume_h1: dict[str, float] = {}   # mint -> previous h1 volume
        self.alerted_at: dict[str, datetime] = {}    # mint -> last alert time
        self.poll_count = 0
        self.alert_count = 0
        self.last_poll: Optional[datetime] = None
        self.last_error: Optional[str] = None

    # ---- lifecycle ----

    async def start(self):
        if not settings.VOLUME_ENABLED:
            logger.info("Volume watcher disabled (VOLUME_ENABLED=false)")
            return
        self.running = True
        self._client = httpx.AsyncClient()
        self.task = asyncio.create_task(self._poll_loop())
        logger.info("Volume watcher started", poll_seconds=settings.VOLUME_POLL_SECONDS)

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
        logger.info("Volume watcher stopped", alerts=self.alert_count)

    def get_status(self) -> dict:
        return {
            "enabled": settings.VOLUME_ENABLED,
            "running": self.running,
            "poll_count": self.poll_count,
            "tokens_watched": len(self.last_volume_h1),
            "alerts_sent": self.alert_count,
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
                logger.warning("Volume poll failed", error=str(e))
            await asyncio.sleep(settings.VOLUME_POLL_SECONDS)

    async def _poll(self):
        if not self._client or not self.launches:
            return
        self.poll_count += 1
        self.last_poll = datetime.now(timezone.utc)

        # Newest tracked launches first: silent pumps are a young-token game.
        mints = list(self.launches.seen_order)[-settings.VOLUME_WATCH_LIMIT:]
        for mint in mints:
            stats = await self._fetch_stats(mint)
            if stats is None:
                continue
            prev = self.last_volume_h1.get(mint)
            self.last_volume_h1[mint] = stats["volume_h1"]
            if not self._in_cooldown(mint) and is_spike(prev, stats):
                await self._alert(mint, stats)

    def _in_cooldown(self, mint: str) -> bool:
        last = self.alerted_at.get(mint)
        if not last:
            return False
        return datetime.now(timezone.utc) - last < timedelta(hours=settings.VOLUME_COOLDOWN_HOURS)

    async def _fetch_stats(self, mint: str) -> Optional[dict]:
        try:
            r = await self._client.get(
                DEXSCREENER_URL.format(mint), timeout=15.0,
                headers={"User-Agent": "narrative-sniper/1.0"},
            )
            r.raise_for_status()
            return parse_pair_stats(r.json())
        except Exception as e:
            logger.debug("Volume stats fetch failed", mint=mint, error=str(e))
            return None

    # ---- alerting ----

    async def _alert(self, mint: str, stats: dict):
        self.alerted_at[mint] = datetime.now(timezone.utc)
        self.alert_count += 1
        symbol = stats["symbol"] or mint[:6]
        buys = stats["buys_h1"]
        volume = stats["volume_h1"]
        # Confidence scales with the size of the buying crowd, capped.
        confidence = min(0.95, 0.7 + buys / 2000.0)
        narrative = Narrative(
            id=str(uuid.uuid4()),
            label=f"Silent buying surge: ${symbol}",
            description=(
                f"{buys} buys in the last hour, ${volume:,.0f} traded — "
                f"and hardly anyone is posting about it."
            ),
            confidence=confidence,
            cluster_size=buys,
            top_tokens=[symbol] if symbol else [],
            sources=[SourceRef(
                platform="dexscreener",
                handle="volume-watcher",
                url=stats["url"] or f"https://dexscreener.com/solana/{mint}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                engagement=buys,
            )],
            token_mint=mint,
            token_symbol=symbol,
            token_name=stats["name"] or symbol,
        )
        logger.info(
            "Volume spike alert",
            symbol=symbol, mint=mint, buys_h1=buys, volume_h1=volume,
        )
        await self.pipeline.emit_narrative(narrative)
