"""Tests that the signal engine records a plain-English verdict on every
narrative (trade_status / trade_reason) for each decision path."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.signals.engine as engine_mod
from app.models import Narrative
from app.signals.engine import SignalEngine


class FakePaper:
    def __init__(self):
        self.opened = []

    async def get_positions(self, status=None):
        return []

    async def open_position(self, **kwargs):
        self.opened.append(kwargs)
        return SimpleNamespace(id="pos-1")


def _narrative(**over):
    base = dict(
        label="Test", description="d", confidence=0.9, cluster_size=20,
        top_tokens=["FOMO"], token_mint="MintFOMO111",
    )
    base.update(over)
    return Narrative(**base)


def _engine(monkeypatch, price=0.5, gate=(True, {})):
    paper = FakePaper()
    eng = SignalEngine(paper)

    async def fake_price(address):
        return price

    eng.prices.price_by_address = fake_price

    async def fake_gate(address):
        return gate

    monkeypatch.setattr(engine_mod, "safety_gate", fake_gate)
    return eng, paper


def test_low_confidence_records_reason(monkeypatch):
    eng, _ = _engine(monkeypatch)
    n = _narrative(confidence=0.5)
    asyncio.run(eng.evaluate(n))
    assert n.trade_status == "not_traded"
    assert "50% sure" in n.trade_reason


def test_small_crowd_records_reason(monkeypatch):
    eng, _ = _engine(monkeypatch)
    n = _narrative(cluster_size=3)
    asyncio.run(eng.evaluate(n))
    assert n.trade_status == "not_traded"
    assert "Crowd too small: 3" in n.trade_reason


def test_no_price_records_reason(monkeypatch):
    eng, _ = _engine(monkeypatch, price=None)
    n = _narrative()
    asyncio.run(eng.evaluate(n))
    assert n.trade_status == "not_traded"
    assert "No live price" in n.trade_reason


def test_safety_block_records_reason(monkeypatch):
    gate = (False, {"score": 82, "verdict": "AVOID", "bottom_line": "One wallet holds 61% of supply."})
    eng, paper = _engine(monkeypatch, gate=gate)
    n = _narrative()
    asyncio.run(eng.evaluate(n))
    assert n.trade_status == "not_traded"
    assert "Failed the safety check" in n.trade_reason
    assert "82/100" in n.trade_reason
    assert paper.opened == []


def test_success_records_traded(monkeypatch):
    eng, paper = _engine(monkeypatch)
    n = _narrative()
    asyncio.run(eng.evaluate(n))
    assert n.trade_status == "traded"
    assert "Bought" in n.trade_reason
    assert len(paper.opened) == 1
    assert paper.opened[0]["token_address"] == "MintFOMO111"
