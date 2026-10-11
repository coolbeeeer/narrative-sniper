"""Volume watcher: the sniper's second pair of eyes.

The social pipeline only hears *talk*. A coin can be bought hard in silence —
no posts, no comments — and the narrative engine would never know. This
watcher polls DexScreener stats for two sets of tokens and raises a
narrative when buying suddenly explodes:

  1. the tokens launch ingestion is tracking (the newest launches, where
     silent pumps are born), and
  2. DexScreener's most-boosted Solana tokens — coins that are taking off
     right now, whatever their age.

A spike is:

  - buys in the last hour >= VOLUME_MIN_BUYS_H1, and
  - volume in the last hour >= VOLUME_MIN_VOLUME_H1_USD, and
  - that volume is at least VOLUME_SPIKE_MULTIPLE x the previous reading
    (first sightings of an already-hot token count too).

The alert is published through pipeline.emit_narrative, so it lands on the
dashboard and goes through the signal engine's normal gates (price lookup,
safety check, cooldowns) before any paper trade opens. A per-token cooldown
stops one pumping coin from spamming alerts. pump.fun Mayhem Mode coins
never alert (see EXCLUDE_MAYHEM_COINS).
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import structlog

from app.core.config import settings
from app.models import Narrative, SourceRef
from app.safety.checker import DEXSCREENER_URL, pumpfun_mayhem_state


logger = structlog.get_logger()

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"


def is_spike(prev_h1_volume: Optional[float], stats: dict,
             min_buys: Optional[int] = None, min_volume: Optional[float] = None) -> bool:
    """Pure spike test, kept separate so it can be unit-tested without I/O.

    With no explicit floors it uses the full-surge settings; the watcher
    passes the lower early-warning floors for its first tier.
    """
    buys = stats.get("buys_h1") or 0
    volume = stats.get("volume_h1") or 0.0
    if buys < (settings.VOLUME_MIN_BUYS_H1 if min_buys is None else min_buys):
        return False
    if volume < (settings.VOLUME_MIN_VOLUME_H1_USD if min_volume is None else min_volume):
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
        "market_cap": pair.get("marketCap") or pair.get("fdv"),
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
        self.alerted_at: dict[str, datetime] = {}    # mint -> last full-surge alert time
        self.early_alerted_at: dict[str, datetime] = {}  # mint -> last early-warning time
        self.boosted_mints: list[str] = []           # latest DexScreener top-boosted set
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
            "boosted_watched": len(self.boosted_mints),
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
        # The window is wide (VOLUME_WATCH_LIMIT) and fetches are batched,
        # so a coin stays watched while its numbers ripen, not just at birth.
        mints = list(self.launches.seen_order)[-settings.VOLUME_WATCH_LIMIT:]
        # Plus the coins taking off right now, of any age (DexScreener's
        # most-boosted list), deduped against the launches.
        if settings.VOLUME_BOOST_ENABLED:
            self.boosted_mints = await self._fetch_boosted_mints()
            for mint in self.boosted_mints:
                if mint not in mints:
                    mints.append(mint)

        stats_by_mint = await self._fetch_stats_batch(mints)
        for mint in mints:
            stats = stats_by_mint.get(mint)
            if stats is None:
                continue
            prev = self.last_volume_h1.get(mint)
            self.last_volume_h1[mint] = stats["volume_h1"]
            if not self._in_cooldown(mint) and is_spike(prev, stats):
                tier = "surge"
            elif (
                not self._in_cooldown(mint, self.early_alerted_at)
                and not self._in_cooldown(mint)
                and is_spike(prev, stats,
                             min_buys=settings.VOLUME_EARLY_MIN_BUYS_H1,
                             min_volume=settings.VOLUME_EARLY_MIN_VOLUME_H1_USD)
            ):
                tier = "early"
            else:
                continue
            if settings.EXCLUDE_MAYHEM_COINS and await pumpfun_mayhem_state(mint, self._client):
                logger.info("Volume alert suppressed: pump.fun Mayhem Mode coin", mint=mint)
                continue
            await self._alert(mint, stats, early=(tier == "early"))

    async def _fetch_stats_batch(self, mints: list[str]) -> dict[str, dict]:
        """DexScreener stats for many mints in a few batched requests
        (the tokens endpoint accepts up to 30 addresses per call)."""
        out: dict[str, dict] = {}
        for i in range(0, len(mints), 30):
            chunk = mints[i:i + 30]
            try:
                r = await self._client.get(
                    DEXSCREENER_URL.format(",".join(chunk)), timeout=20.0,
                    headers={"User-Agent": "narrative-sniper/1.0"},
                )
                r.raise_for_status()
                payload = r.json()
            except Exception as e:
                logger.debug("Volume batch fetch failed", error=str(e))
                continue
            pairs = payload if isinstance(payload, list) else (payload or {}).get("pairs") or []
            by_mint: dict[str, list] = {}
            for pair in pairs:
                addr = (pair.get("baseToken") or {}).get("address")
                if addr:
                    by_mint.setdefault(addr, []).append(pair)
            for mint in chunk:
                stats = parse_pair_stats(by_mint.get(mint) or [])
                if stats is not None:
                    out[mint] = stats
        return out

    async def _fetch_boosted_mints(self) -> list[str]:
        """Solana mints from DexScreener's most-boosted list (top first)."""
        try:
            r = await self._client.get(
                DEXSCREENER_BOOSTS_URL, timeout=15.0,
                headers={"User-Agent": "narrative-sniper/1.0"},
            )
            r.raise_for_status()
            entries = r.json() or []
        except Exception as e:
            logger.debug("Boosted tokens fetch failed", error=str(e))
            return []
        out: list[str] = []
        for entry in entries:
            if (entry.get("chainId") or "").lower() != "solana":
                continue
            mint = entry.get("tokenAddress")
            if mint and mint not in out:
                out.append(mint)
            if len(out) >= settings.VOLUME_BOOST_LIMIT:
                break
        return out

    def _in_cooldown(self, mint: str, mapping: Optional[dict] = None) -> bool:
        last = (self.alerted_at if mapping is None else mapping).get(mint)
        if not last:
            return False
        return datetime.now(timezone.utc) - last < timedelta(hours=settings.VOLUME_COOLDOWN_HOURS)

    # ---- alerting ----

    async def _alert(self, mint: str, stats: dict, early: bool = False):
        now = datetime.now(timezone.utc)
        if early:
            self.early_alerted_at[mint] = now
        else:
            self.alerted_at[mint] = now
        self.alert_count += 1
        symbol = stats["symbol"] or mint[:6]
        buys = stats["buys_h1"]
        volume = stats["volume_h1"]
        market_cap = stats.get("market_cap")
        mc_clause = f" Caught at ${market_cap:,.0f} market cap." if market_cap else ""
        if early:
            label = f"Early buying activity: ${symbol}"
            description = (
                f"Early warning on a small coin: {buys} buys in the last hour, "
                f"${volume:,.0f} traded.{mc_clause} Shown early — the usual "
                f"safety rules still judge it before any trade."
            )
            # Deliberately modest: early warnings are a heads-up, not a call.
            confidence = min(0.85, 0.65 + buys / 2000.0)
        else:
            label = f"Silent buying surge: ${symbol}"
            description = (
                f"{buys} buys in the last hour, ${volume:,.0f} traded — "
                f"and hardly anyone is posting about it.{mc_clause}"
            )
            # Confidence scales with the size of the buying crowd, capped.
            confidence = min(0.95, 0.7 + buys / 2000.0)
        narrative = Narrative(
            id=str(uuid.uuid4()),
            label=label,
            description=description,
            confidence=confidence,
            cluster_size=buys,
            top_tokens=[symbol] if symbol else [],
            sources=[SourceRef(
                platform="dexscreener",
                handle="volume-watcher",
                url=stats["url"] or f"https://dexscreener.com/solana/{mint}",
                timestamp=now.isoformat(),
                engagement=buys,
            )],
            token_mint=mint,
            token_symbol=symbol,
            token_name=stats["name"] or symbol,
            caught_market_cap=float(market_cap) if market_cap else None,
        )
        logger.info(
            "Volume spike alert",
            symbol=symbol, mint=mint, buys_h1=buys, volume_h1=volume,
            market_cap=market_cap, early=early,
        )
        await self.pipeline.emit_narrative(narrative)
