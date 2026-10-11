"""Live trading engine: real-money positions with the same interface as
the paper engine, so the signal engine can trade through either.

Differences that matter:
  - Buys and sells are real Jupiter swaps signed by the bot wallet.
  - Positions are persisted to disk (LIVE_POSITIONS_FILE) and reconciled
    against the wallet's actual token balances at startup — a restart
    never forgets real money.
  - A daily loss limit halts new buys once today's realized losses pass
    LIVE_DAILY_LOSS_LIMIT_USD.
  - Sells always dispose of the wallet's full actual balance of the mint
    (chain ground truth), not the book amount.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from app.core.config import settings
from app.live.jupiter import JupiterClient, JupiterError
from app.live.wallet import BotWallet
from app.models import PnLDataPoint, Position


logger = structlog.get_logger()


class LiveTradingEngine:
    def __init__(self, wallet: BotWallet, jupiter: JupiterClient):
        self.wallet = wallet
        self.jupiter = jupiter
        self.positions: dict[str, Position] = {}

    # ---- persistence ----

    def _file(self) -> Path:
        return Path(settings.LIVE_POSITIONS_FILE)

    def _persist(self):
        try:
            path = self._file()
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [p.model_dump(mode="json") for p in self.positions.values()]
            path.write_text(json.dumps(data, indent=1))
        except Exception as e:
            logger.error("Could not persist live positions", error=str(e))

    def _load(self):
        path = self._file()
        if not path.exists():
            return
        try:
            for raw in json.loads(path.read_text()):
                pos = Position.model_validate(raw)
                self.positions[pos.id] = pos
            logger.info("Live positions loaded", count=len(self.positions))
        except Exception as e:
            logger.error("Could not load live positions file", error=str(e))

    async def initialize(self):
        """Load persisted positions and reconcile with on-chain balances."""
        self._load()
        for pos in list(self.positions.values()):
            if pos.status != "open":
                continue
            bal = await self.wallet.token_balance(pos.token_address)
            if bal is not None and bal["raw"] == 0:
                # The tokens are gone (sold elsewhere, or a sell landed
                # while we were down). Close the book entry; proceeds are
                # unknown, so realized PnL is recorded as 0 with a warning.
                pos.status = "closed"
                pos.exit_time = datetime.utcnow()
                pos.exit_price = pos.entry_price
                pos.realized_pnl = 0.0
                logger.warning(
                    "Live position reconciled closed: wallet holds none of this token",
                    symbol=pos.token_symbol, mint=pos.token_address,
                )
        self._persist()

    # ---- risk ----

    def realized_today_usd(self) -> float:
        today = datetime.utcnow().date()
        return sum(
            p.realized_pnl for p in self.positions.values()
            if p.status == "closed" and p.exit_time and p.exit_time.date() == today
        )

    def halted_today(self) -> bool:
        return self.realized_today_usd() <= -abs(settings.LIVE_DAILY_LOSS_LIMIT_USD)

    # ---- interface mirroring the paper engine ----

    async def get_positions(
        self, status: Optional[str] = None, narrative_id: Optional[str] = None
    ) -> list[Position]:
        out = list(self.positions.values())
        if status:
            out = [p for p in out if p.status == status]
        if narrative_id:
            out = [p for p in out if p.narrative_id == narrative_id]
        return out

    async def get_position(self, position_id: str) -> Optional[Position]:
        return self.positions.get(position_id)

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
        # The paper-style amount/entry_price arguments are ignored for
        # sizing: a live buy spends the configured USD size at the real
        # Jupiter price, and the position records what actually arrived.
        if self.halted_today():
            raise ValueError(
                f"Live daily loss limit hit (${self.realized_today_usd():,.2f} today) — no new live buys until tomorrow"
            )
        size_usd = min(settings.SIGNAL_POSITION_SIZE_USD, settings.MAX_POSITION_SIZE_USD)
        sol_price = await self.jupiter.sol_price_usd()
        sol_needed = size_usd / sol_price

        balance = await self.wallet.sol_balance()
        if balance is None:
            raise ValueError("Could not read the bot wallet's SOL balance")
        if balance - sol_needed < settings.LIVE_MIN_SOL_RESERVE:
            raise ValueError(
                f"Bot wallet holds {balance:.4f} SOL — topping it up is required before this buy"
            )

        result = await self.jupiter.buy(token_address, sol_needed)
        held = await self.wallet.token_balance(token_address)
        if not held or held["human"] <= 0:
            raise JupiterError(
                "Buy was confirmed but the wallet shows no tokens — check the wallet before the next trade"
            )
        actual_amount = held["human"]
        actual_entry = size_usd / actual_amount

        import uuid
        position = Position(
            id=str(uuid.uuid4()),
            token_address=token_address,
            token_symbol=token_symbol,
            token_name=token_name,
            entry_price=actual_entry,
            current_price=actual_entry,
            amount=actual_amount,
            value_usd=size_usd,
            pnl_usd=0.0,
            pnl_percent=0.0,
            narrative_id=narrative_id,
            narrative_label=narrative_label,
            entry_time=datetime.utcnow(),
            entry_market_cap=entry_market_cap,
            status="open",
            tx_signature=result["signature"],
        )
        self.positions[position.id] = position
        self._persist()
        logger.info(
            "Live position opened", symbol=token_symbol, size_usd=size_usd,
            signature=result["signature"],
        )
        return position

    async def close_position(
        self, position_id: str, exit_price: Optional[float] = None
    ) -> Optional[Position]:
        position = self.positions.get(position_id)
        if not position or position.status != "open":
            return None

        cost_usd = position.amount * position.entry_price
        held = await self.wallet.token_balance(position.token_address)
        if held is not None and held["raw"] > 0:
            result = await self.jupiter.sell(position.token_address, held["raw"])
            sol_price = await self.jupiter.sol_price_usd()
            proceeds_usd = (result["out_lamports"] / 1_000_000_000) * sol_price
            real_exit = proceeds_usd / held["human"] if held["human"] else (exit_price or position.entry_price)
            position.exit_tx_signature = result["signature"]
        else:
            # Nothing left to sell (already gone) — settle at the
            # indicative price so the book matches reality as best known.
            real_exit = exit_price or position.entry_price
            proceeds_usd = position.amount * real_exit
            logger.warning(
                "Live close with no tokens held; settled at indicative price",
                symbol=position.token_symbol,
            )

        position.exit_price = real_exit
        position.current_price = real_exit
        position.exit_time = datetime.utcnow()
        position.status = "closed"
        position.realized_pnl = proceeds_usd - cost_usd
        position.value_usd = proceeds_usd
        position.pnl_usd = position.realized_pnl
        position.pnl_percent = (
            (real_exit - position.entry_price) / position.entry_price * 100
            if position.entry_price else 0.0
        )
        self._persist()
        logger.info(
            "Live position closed", symbol=position.token_symbol,
            realized_pnl=round(position.realized_pnl, 2),
        )
        return position

    async def get_pnl_history(self, range: str) -> list[PnLDataPoint]:
        points: list[PnLDataPoint] = []
        realized = 0.0
        closed = sorted(
            (p for p in self.positions.values() if p.status == "closed" and p.exit_time),
            key=lambda p: p.exit_time,
        )
        for p in closed:
            realized += p.realized_pnl
            points.append(PnLDataPoint(
                timestamp=p.exit_time,
                total_value=realized,
                realized_pnl=realized,
                unrealized_pnl=0.0,
            ))
        open_unrealized = sum(p.pnl_usd for p in self.positions.values() if p.status == "open")
        open_value = sum(p.value_usd for p in self.positions.values() if p.status == "open")
        points.append(PnLDataPoint(
            timestamp=datetime.utcnow(),
            total_value=open_value + realized,
            realized_pnl=realized,
            unrealized_pnl=open_unrealized,
        ))
        return points
