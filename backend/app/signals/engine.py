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
from app.safety.checker import safety_gate
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

    @staticmethod
    def _decide(narrative: Narrative, traded: bool, reason: str):
        """Record the verdict on the narrative itself, in plain words, so
        the dashboard can explain why a story was or was not traded."""
        narrative.trade_status = "traded" if traded else "not_traded"
        narrative.trade_reason = reason

    async def evaluate(self, narrative: Narrative):
        """Called by the intelligence pipeline for every new narrative."""
        if not settings.SIGNAL_ENABLED:
            self._decide(narrative, False, "The sniper is switched off in its settings.")
            return

        symbol = self._pick_symbol(narrative)
        reasons: list[str] = []
        plain_reasons: list[str] = []

        if narrative.confidence < settings.SIGNAL_CONFIDENCE_THRESHOLD:
            reasons.append(f"confidence {narrative.confidence:.2f} < {settings.SIGNAL_CONFIDENCE_THRESHOLD}")
            plain_reasons.append(
                f"Only {narrative.confidence * 100:.0f}% sure — it needs "
                f"{settings.SIGNAL_CONFIDENCE_THRESHOLD * 100:.0f}% before buying."
            )
        if narrative.cluster_size < settings.SIGNAL_MIN_CLUSTER_SIZE:
            reasons.append(f"cluster size {narrative.cluster_size} < {settings.SIGNAL_MIN_CLUSTER_SIZE}")
            plain_reasons.append(
                f"Crowd too small: {narrative.cluster_size} — it needs "
                f"{settings.SIGNAL_MIN_CLUSTER_SIZE}."
            )
        if not symbol:
            reasons.append("no tradeable token symbol")
            plain_reasons.append("No coin was named clearly enough to buy.")

        if reasons:
            logger.debug("Signal rejected", narrative=narrative.label, reasons=reasons)
            self._decide(narrative, False, " ".join(plain_reasons))
            return

        # duplicate / cooldown checks
        open_positions = await self.paper_trading.get_positions(status="open")
        if any(p.token_symbol == symbol for p in open_positions):
            logger.debug("Signal rejected: already holding", symbol=symbol)
            self._decide(narrative, False, f"Already holding ${symbol}.")
            return
        last = self.last_trade_at.get(symbol)
        if last and datetime.utcnow() - last < timedelta(hours=settings.SIGNAL_COOLDOWN_HOURS):
            logger.debug("Signal rejected: cooldown", symbol=symbol)
            self._decide(narrative, False, f"${symbol} was traded recently — cooling down before buying it again.")
            return
        if len(open_positions) >= settings.SIGNAL_MAX_OPEN_POSITIONS:
            logger.debug("Signal rejected: max open positions reached")
            self._decide(narrative, False, f"Too many trades already open (max {settings.SIGNAL_MAX_OPEN_POSITIONS}).")
            return

        # resolve price (free DexScreener lookup)
        # Prefer the exact mint propagated from ingestion over symbol guessing:
        # a funded impostor can share a symbol, but never the mint.
        quote: Optional[dict] = None
        if getattr(narrative, "token_mint", None):
            price = await self.prices.price_by_address(narrative.token_mint)
            if price:
                quote = {
                    "address": narrative.token_mint,
                    "symbol": symbol,
                    "name": narrative.label,
                    "price_usd": price,
                }
            else:
                logger.info("Signal rejected: no price for narrative mint", mint=narrative.token_mint)
                self._decide(narrative, False, "No live price could be found for this coin.")
                return
        else:
            quote = await self.prices.resolve_symbol(symbol)
            if not quote or not quote.get("address"):
                logger.info("Signal rejected: no Solana price found", symbol=symbol)
                self._decide(narrative, False, f"${symbol} could not be found trading on Solana.")
                return

        # safety gate: rug checks before any paper position opens
        allowed, report = await safety_gate(quote["address"])
        if not allowed:
            logger.info(
                "Signal rejected by safety gate",
                symbol=symbol,
                mint=quote["address"],
                score=report.get("score"),
                verdict=report.get("verdict"),
            )
            await self._emit({
                "type": "trade_rejected_safety",
                "symbol": symbol,
                "narrative": narrative.label,
                "mint": quote["address"],
                "score": report.get("score"),
                "verdict": report.get("verdict"),
                "bottom_line": report.get("bottom_line"),
            })
            bottom = (report.get("bottom_line") or "").strip()
            score = report.get("score")
            reason = "Failed the safety check"
            if score is not None:
                reason += f" (risk score {score}/100)"
            reason += f": {bottom}" if bottom else "."
            self._decide(narrative, False, reason)
            return

        price = quote["price_usd"]
        size_usd = min(settings.SIGNAL_POSITION_SIZE_USD, settings.MAX_POSITION_SIZE_USD)
        amount = size_usd / price
        if amount <= 0:
            self._decide(narrative, False, "The trade size worked out to nothing at this price.")
            return

        # Market cap at the moment of the buy: from the quote when the
        # symbol lookup carried it, else a direct lookup for the mint,
        # else what the volume watcher recorded when it caught the coin.
        entry_market_cap = quote.get("market_cap")
        if not entry_market_cap:
            entry_market_cap = await self.prices.market_cap_by_address(quote["address"])
        if not entry_market_cap:
            entry_market_cap = getattr(narrative, "caught_market_cap", None)

        try:
            position = await self.paper_trading.open_position(
                token_address=quote["address"],
                token_symbol=quote["symbol"],
                token_name=quote["name"],
                entry_price=price,
                amount=amount,
                narrative_id=narrative.id,
                narrative_label=narrative.label,
                entry_market_cap=float(entry_market_cap) if entry_market_cap else None,
            )
        except ValueError as e:
            logger.warning("Signal rejected by risk limits", symbol=symbol, error=str(e))
            self._decide(narrative, False, f"Blocked by the risk limits: {e}")
            return

        self.last_trade_at[symbol] = datetime.utcnow()
        if entry_market_cap:
            reason = (
                f"Bought ${size_usd:,.0f} worth at ${price:g}, "
                f"at a ${entry_market_cap:,.0f} market cap — see it under Trades."
            )
        else:
            reason = f"Bought ${size_usd:,.0f} worth at ${price:g} — see it under Trades."
        self._decide(narrative, True, reason)
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
