"""The paper engine stores the market cap at entry on the position."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paper_trading.engine import PaperTradingEngine


def test_open_position_stores_entry_market_cap():
    eng = PaperTradingEngine()
    pos = asyncio.run(eng.open_position(
        token_address="MintX", token_symbol="X", token_name="X Coin",
        entry_price=0.5, amount=100.0,
        narrative_id="n1", narrative_label="L",
        entry_market_cap=123_456.0,
    ))
    assert pos.entry_market_cap == 123_456.0


def test_open_position_entry_market_cap_defaults_none():
    eng = PaperTradingEngine()
    pos = asyncio.run(eng.open_position(
        token_address="MintX", token_symbol="X", token_name="X Coin",
        entry_price=0.5, amount=100.0,
        narrative_id="n1", narrative_label="L",
    ))
    assert pos.entry_market_cap is None
