import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional
from decimal import Decimal
import structlog

from app.core.config import settings
from app.models import Position, PnLDataPoint
from app.execution.engine import ExecutionEngine


logger = structlog.get_logger()


class PaperTradingEngine:
    def __init__(self):
        self.positions: dict[str, Position] = {}
        self.pnl_history: list[PnLDataPoint] = []
        self.initial_balance_usd = 10000.0
        self.current_balance_usd = self.initial_balance_usd
        self.daily_pnl = 0.0
        self.daily_start_balance = self.initial_balance_usd
        self.last_pnl_update = datetime.utcnow()
        self.price_cache: dict[str, float] = {}
        self.running = False
        self.update_task: Optional[asyncio.Task] = None
        self.execution_engine: Optional[ExecutionEngine] = None

    async def initialize(self):
        self.running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("Paper trading engine initialized", initial_balance=self.initial_balance_usd)

    async def shutdown(self):
        self.running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("Paper trading engine shutdown")

    def set_execution_engine(self, engine: ExecutionEngine):
        self.execution_engine = engine

    async def _update_loop(self):
        while self.running:
            try:
                await self._update_prices()
                await self._record_pnl_snapshot()
                await self._check_risk_limits()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Paper trading update error", error=str(e))
                await asyncio.sleep(5)

    async def _update_prices(self):
        if not self.execution_engine:
            return

        for position in self.positions.values():
            if position.status != "open":
                continue

            try:
                price = await self.execution_engine.get_token_price(position.token_address)
                if price:
                    position.current_price = price
                    position.value_usd = position.amount * price
                    position.pnl_usd = position.value_usd - (position.amount * position.entry_price)
                    position.pnl_percent = (
                        (position.current_price - position.entry_price) / position.entry_price * 100
                    )
            except Exception as e:
                logger.error("Failed to update price", token=position.token_address, error=str(e))

    async def _record_pnl_snapshot(self):
        open_positions = [p for p in self.positions.values() if p.status == "open"]
        total_value = self.current_balance_usd + sum(p.value_usd for p in open_positions)
        realized_pnl = sum(p.realized_pnl for p in self.positions.values() if p.status == "closed")
        unrealized_pnl = sum(p.pnl_usd for p in open_positions)

        self.pnl_history.append(PnLDataPoint(
            timestamp=datetime.utcnow(),
            total_value=total_value,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
        ))

        # Keep last 10000 points
        if len(self.pnl_history) > 10000:
            self.pnl_history = self.pnl_history[-10000:]

    async def _check_risk_limits(self):
        open_positions = [p for p in self.positions.values() if p.status == "open"]
        total_exposure = sum(p.value_usd for p in open_positions)

        if total_exposure > settings.MAX_POSITION_SIZE_USD * 10:  # Portfolio limit
            logger.warning("Portfolio exposure limit exceeded", exposure=total_exposure)

        # Daily loss limit
        daily_loss = self.daily_start_balance - self.current_balance_usd - sum(
            p.pnl_usd for p in open_positions
        )
        if daily_loss > settings.MAX_DAILY_LOSS_USD:
            logger.warning("Daily loss limit exceeded", loss=daily_loss)

    async def open_position(
        self,
        token_address: str,
        token_symbol: str,
        token_name: str,
        entry_price: float,
        amount: float,
        narrative_id: str,
        narrative_label: str,
        entry_market_cap: Optional[float] = None,
    ) -> Position:
        cost = amount * entry_price
        
        if cost > self.current_balance_usd:
            raise ValueError("Insufficient balance")

        if cost > settings.MAX_POSITION_SIZE_USD:
            raise ValueError(f"Position size exceeds max: {settings.MAX_POSITION_SIZE_USD}")

        self.current_balance_usd -= cost

        position = Position(
            id=str(uuid.uuid4()),
            token_address=token_address,
            token_symbol=token_symbol,
            token_name=token_name,
            entry_price=entry_price,
            current_price=entry_price,
            amount=amount,
            value_usd=cost,
            pnl_usd=0.0,
            pnl_percent=0.0,
            narrative_id=narrative_id,
            narrative_label=narrative_label,
            entry_time=datetime.utcnow(),
            entry_market_cap=entry_market_cap,
            status="open",
        )

        self.positions[position.id] = position
        logger.info("Paper position opened", position_id=position.id, token=token_symbol, cost=cost)

        return position

    async def close_position(self, position_id: str, exit_price: Optional[float] = None) -> Optional[Position]:
        position = self.positions.get(position_id)
        if not position or position.status != "open":
            return None

        if exit_price is None:
            exit_price = position.current_price

        position.exit_price = exit_price
        position.exit_time = datetime.utcnow()
        position.status = "closed"
        position.realized_pnl = position.amount * (exit_price - position.entry_price)
        position.pnl_usd = position.realized_pnl
        position.pnl_percent = (
            (exit_price - position.entry_price) / position.entry_price * 100
        )

        self.current_balance_usd += position.amount * exit_price

        logger.info("Paper position closed", position_id=position_id, realized_pnl=position.realized_pnl)

        return position

    async def partial_close(self, position_id: str, amount: float, exit_price: Optional[float] = None) -> Optional[Position]:
        position = self.positions.get(position_id)
        if not position or position.status != "open":
            return None

        if amount >= position.amount:
            return await self.close_position(position_id, exit_price)

        if exit_price is None:
            exit_price = position.current_price

        realized = amount * (exit_price - position.entry_price)
        position.amount -= amount
        position.value_usd = position.amount * position.current_price
        position.realized_pnl += realized
        position.pnl_usd = position.amount * (position.current_price - position.entry_price) + position.realized_pnl

        self.current_balance_usd += amount * exit_price

        if position.amount <= 0:
            position.status = "closed"
            position.exit_time = datetime.utcnow()

        logger.info("Paper position partially closed", position_id=position_id, amount=amount, realized=realized)

        return position

    async def get_positions(
        self,
        status: Optional[str] = None,
        narrative_id: Optional[str] = None,
    ) -> list[Position]:
        positions = list(self.positions.values())
        
        if status:
            positions = [p for p in positions if p.status == status]
        if narrative_id:
            positions = [p for p in positions if p.narrative_id == narrative_id]
        
        positions.sort(key=lambda x: x.entry_time, reverse=True)
        return positions

    async def get_position(self, position_id: str) -> Optional[Position]:
        return self.positions.get(position_id)

    async def get_pnl_history(self, range: str) -> list[PnLDataPoint]:
        now = datetime.utcnow()
        if range == "1h":
            cutoff = now - timedelta(hours=1)
        elif range == "24h":
            cutoff = now - timedelta(days=1)
        elif range == "7d":
            cutoff = now - timedelta(days=7)
        elif range == "30d":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(days=1)

        return [p for p in self.pnl_history if p.timestamp >= cutoff]

    async def get_open_positions_count(self) -> int:
        return len([p for p in self.positions.values() if p.status == "open"])

    def get_portfolio_summary(self) -> dict:
        open_positions = [p for p in self.positions.values() if p.status == "open"]
        total_value = self.current_balance_usd + sum(p.value_usd for p in open_positions)
        total_pnl = sum(p.pnl_usd for p in open_positions) + sum(p.realized_pnl for p in self.positions.values() if p.status == "closed")
        
        return {
            "initial_balance": self.initial_balance_usd,
            "current_balance": self.current_balance_usd,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_percent": (total_value - self.initial_balance_usd) / self.initial_balance_usd * 100,
            "open_positions": len(open_positions),
            "total_positions": len(self.positions),
            "daily_pnl": self.daily_pnl,
        }