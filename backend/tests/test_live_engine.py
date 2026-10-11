"""Live engine: real-money bookkeeping with wallet + Jupiter faked.

Covers: open records what actually arrived and persists to disk; a fresh
engine reloads positions; insufficient SOL blocks the buy; a TP exit
books the real proceeds; the daily loss limit halts further buys; boot
reconciliation closes positions whose tokens are gone.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.live.engine import LiveTradingEngine


class FakeWallet:
    def __init__(self, sol=2.0):
        self._sol = sol
        self.holdings: dict[str, dict] = {}
        self.address = "FakeWallet111"

    async def sol_balance(self):
        return self._sol

    async def token_balance(self, mint):
        return self.holdings.get(mint, {"raw": 0, "decimals": 6, "human": 0.0})


class FakeJupiter:
    def __init__(self, wallet: FakeWallet, sell_lamports=1_100_000_000):
        self.wallet = wallet
        self.sell_lamports = sell_lamports

    async def sol_price_usd(self):
        return 100.0

    async def buy(self, mint, sol_amount):
        self.wallet.holdings[mint] = {"raw": 200_000_000, "decimals": 6, "human": 200.0}
        return {"signature": "BuySig", "out_raw": 200_000_000}

    async def sell(self, mint, amount_raw):
        self.wallet.holdings[mint] = {"raw": 0, "decimals": 6, "human": 0.0}
        return {"signature": "SellSig", "out_lamports": self.sell_lamports}


def _engine(tmp_path, monkeypatch, sol=2.0, sell_lamports=1_100_000_000):
    monkeypatch.setattr(settings, "LIVE_POSITIONS_FILE", str(tmp_path / "live.json"))
    wallet = FakeWallet(sol=sol)
    return LiveTradingEngine(wallet, FakeJupiter(wallet, sell_lamports)), wallet


def _open(eng):
    return asyncio.run(eng.open_position(
        token_address="MintLIVE", token_symbol="LIVE", token_name="Live Coin",
        entry_price=1.0, amount=1.0, narrative_id="n1", narrative_label="L",
        entry_market_cap=50_000.0,
    ))


def test_open_records_actual_fill_and_persists(tmp_path, monkeypatch):
    eng, wallet = _engine(tmp_path, monkeypatch)
    pos = _open(eng)
    assert pos.amount == 200.0            # what the wallet actually holds
    assert pos.entry_price == 0.5         # $100 size / 200 tokens
    assert pos.tx_signature == "BuySig"
    assert pos.entry_market_cap == 50_000.0

    # A fresh engine over the same wallet + positions file reloads it,
    # and reconciliation keeps it open because the wallet still holds it.
    eng2 = LiveTradingEngine(wallet, FakeJupiter(wallet))
    asyncio.run(eng2.initialize())
    loaded = asyncio.run(eng2.get_positions())
    assert len(loaded) == 1
    assert loaded[0].token_symbol == "LIVE"
    assert loaded[0].status == "open"


def test_open_blocked_when_wallet_short(tmp_path, monkeypatch):
    eng, _ = _engine(tmp_path, monkeypatch, sol=0.5)  # needs 1.0 SOL + reserve
    try:
        _open(eng)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "SOL" in str(e)


def test_close_books_real_proceeds(tmp_path, monkeypatch):
    eng, _ = _engine(tmp_path, monkeypatch)  # sell returns 1.1 SOL = $110 on a $100 buy
    pos = _open(eng)
    closed = asyncio.run(eng.close_position(pos.id, exit_price=0.6))
    assert closed.status == "closed"
    assert abs(closed.realized_pnl - 10.0) < 0.01
    assert closed.exit_tx_signature == "SellSig"


def test_daily_loss_limit_halts_buys(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_DAILY_LOSS_LIMIT_USD", 50.0)
    eng, _ = _engine(tmp_path, monkeypatch, sell_lamports=100_000_000)  # 0.1 SOL = $10 back
    pos = _open(eng)
    closed = asyncio.run(eng.close_position(pos.id, exit_price=0.05))
    assert abs(closed.realized_pnl - (-90.0)) < 0.01
    assert eng.halted_today()
    try:
        _open(eng)
        assert False, "expected the daily loss halt"
    except ValueError as e:
        assert "daily loss limit" in str(e).lower()


def test_reconcile_closes_positions_with_no_tokens(tmp_path, monkeypatch):
    eng, wallet = _engine(tmp_path, monkeypatch)
    pos = _open(eng)
    wallet.holdings.clear()  # tokens vanished (sold elsewhere / wallet moved)
    eng2, _ = _engine(tmp_path, monkeypatch)
    eng2.wallet.holdings.clear()
    asyncio.run(eng2.initialize())
    loaded = asyncio.run(eng2.get_position(pos.id))
    assert loaded.status == "closed"
