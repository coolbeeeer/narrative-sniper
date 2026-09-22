"""Decision bridge: turns high-confidence narratives into paper trades.

Rules for entering a trade:
  1. Narrative confidence >= SIGNAL_CONFIDENCE_THRESHOLD
  2. Cluster size (mention velocity) >= SIGNAL_MIN_CLUSTER_SIZE
  3. At least one token symbol detected, resolvable to a Solana price
  4. No open position on that token already, and no trade on it within the cooldown window
  5. Fewer than SIGNAL_MAX_OPEN_POSITIONS open positions

Exits: a background monitor closes positions at take-profit / stop-loss.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, Awaitable
import structlog

from app.core.config import settings
from app.models import Narrative
from app.paper_trading.engine import PaperTradingEngine
from app.signals.prices import PriceLookup


logger = structlog.get_logger()


class SignalEngine:
    def __init__(
        self,
        paper_trading: PaperTradingEngine,
        on_event: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.paper_trading = paper_trading
        self.prices = PriceLookup()
        self.on_event = on_event
        self.last_trade_at: dict[str, datetime] = {}  # symbol -> last entry time
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None

    async def start(self):
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Signal engine started")

    async def stop(self):
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Signal engine stopped")

    async def _emit(self, event: dict):
        logger.info("Signal event", **event)
        if self.on_event:
            try:
                await self.on_event(event)
            except Exception as e:
                logger.warning("Signal event broadcast failed", error=str(e))

    # ---- entry ----

    async def evaluate(self, narrative: Narrative):
        """Called by the intelligence pipeline for every new narrative."""
        if not settings.SIGNAL_ENABLED:
            return

        symbol = self._pick_symbol(narrative)
        reasons: list[str] = []

        if narrative.confidence < settings.SIGNAL_CONFIDENCE_THRESHOLD:
            reasons.append(f"confidence {narrative.confidence:.2f} < {settings.SIGNAL_CONFIDENCE_THRESHOLD}")
        if narrative.cluster_size < settings.SIGNAL_MIN_CLUSTER_SIZE:
            reasons.append(f"cluster size {narrative.cluster_size} < {settings.SIGNAL_MIN_CLUSTER_SIZE}")
        if not symbol:
            reasons.append("no tradeable token symbol")

        if reasons:
            logger.debug("Signal rejected", narrative=narrative.label, reasons=reasons)
            return

        # duplicate / cooldown checks
        open_positions = await self.paper_trading.get_positions(status="open")
        if any(p.token_symbol == symbol for p in open_positions):
            logger.debug("Signal rejected: already holding", symbol=symbol)
            return
        last = self.last_trade_at.get(symbol)
        if last and datetime.utcnow() - last < timedelta(hours=settings.SIGNAL_COOLDOWN_HOURS):
            logger.debug("Signal rejected: cooldown", symbol=symbol)
            return
        if len(open_positions) >= settings.SIGNAL_MAX_OPEN_POSITIONS:
            logger.debug("Signal rejected: max open positions reached")
            return

        # resolve price (free DexScreener lookup)
        quote = await self.prices.resolve_symbol(symbol)
        if not quote or not quote.get("address"):
            logger.info("Signal rejected: no Solana price found", symbol=symbol)
            return

        price = quote["price_usd"]
        size_usd = min(settings.SIGNAL_POSITION_SIZE_USD, settings.MAX_POSITION_SIZE_USD)
        amount = size_usd / price
        if amount <= 0:
            return

        try:
            position = await self.paper_trading.open_position(
                token_address=quote["address"],
                token_symbol=quote["symbol"],
                token_name=quote["name"],
                entry_price=price,
                amount=amount,
                narrative_id=narrative.id,
                narrative_label=narrative.label,
            )
        except ValueError as e:
            logger.warning("Signal rejected by risk limits", symbol=symbol, error=str(e))
            return

        self.last_trade_at[symbol] = datetime.utcnow()
        await self._emit({
            "type": "trade_opened",
            "symbol": quote["symbol"],
            "narrative": narrative.label,
            "confidence": round(narrative.confidence, 3),
            "entry_price": price,
            "size_usd": round(size_usd, 2),
            "position_id": position.id,
        })

    def _pick_symbol(self, narrative: Narrative) -> Optional[str]:
        tokens = [t for t in (narrative.top_tokens or []) if t]
        if not tokens:
            return None
        # skip obvious non-tradeable mentions
        skip = {"SOL", "USD", "USDT", "USDC"}
        for t in tokens:
            if t.upper() not in skip:
                return t.upper()
        return None

    # ---- exits ----

    async def _monitor_loop(self):
        while self.running:
            try:
                await self._check_exits()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Signal monitor error", error=str(e))
            await asyncio.sleep(60)

    async def _check_exits(self):
        positions = await self.paper_trading.get_positions(status="open")
        for position in positions:
            price = await self.prices.price_by_address(position.token_address)
            if not price:
                continue

            # keep the paper engine's numbers fresh
            position.current_price = price
            position.value_usd = position.amount * price
            position.pnl_usd = position.value_usd - (position.amount * position.entry_price)
            position.pnl_percent = (price - position.entry_price) / position.entry_price * 100

            pnl = position.pnl_percent
            if pnl >= settings.SIGNAL_TAKE_PROFIT_PCT:
                await self._close(position, price, "take_profit", pnl)
            elif pnl <= -settings.SIGNAL_STOP_LOSS_PCT:
                await self._close(position, price, "stop_loss", pnl)

    async def _close(self, position, price: float, reason: str, pnl_pct: float):
        closed = await self.paper_trading.close_position(position.id, exit_price=price)
        if closed:
            await self._emit({
                "type": "trade_closed",
                "symbol": position.token_symbol,
                "reason": reason,
                "pnl_percent": round(pnl_pct, 2),
                "realized_pnl_usd": round(closed.realized_pnl, 2),
                "position_id": position.id,
            })
