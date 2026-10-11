"""Live mode switching: the config API guards, and the signal engine's
routing between the paper and live engines."""
import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main
from app.core.config import settings
from app.models import Narrative
from app.signals.engine import SignalEngine


@pytest.fixture()
def client():
    # The sandbox proxy env breaks the TestClient's httpx transport;
    # drop it for the app session and restore afterwards.
    saved = {}
    for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                "no_proxy", "NO_PROXY", "all_proxy", "ALL_PROXY"):
        if var in os.environ:
            saved[var] = os.environ.pop(var)
    try:
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        os.environ.update(saved)


@pytest.fixture(autouse=True)
def _restore_mode():
    yield
    settings.LIVE_TRADING_ENABLED = False
    settings.PAPER_TRADING = True


def test_wallet_status_unconfigured(client):
    r = client.get("/api/wallet/status")
    assert r.status_code == 200
    assert r.json()["configured"] is False
    assert r.json()["address"] is None


def test_enabling_live_requires_confirmation(client):
    r = client.patch("/api/config", json={"live_trading_enabled": True})
    assert r.status_code == 422


def test_enabling_live_requires_wallet(client):
    r = client.patch(
        "/api/config",
        json={"live_trading_enabled": True, "confirm_live": "LIVE"},
    )
    assert r.status_code == 422
    assert "wallet" in r.json()["detail"].lower()


def test_enable_and_disable_live_with_wallet(client, monkeypatch):
    monkeypatch.setattr(main, "live_trading_engine", object())
    r = client.patch(
        "/api/config",
        json={"live_trading_enabled": True, "confirm_live": "LIVE"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["live_trading_enabled"] is True
    assert body["paper_trading"] is False

    r = client.patch("/api/config", json={"live_trading_enabled": False})
    assert r.status_code == 200
    assert r.json()["live_trading_enabled"] is False
    assert r.json()["paper_trading"] is True


class RecordingEngine:
    def __init__(self):
        self.opened = []

    async def get_positions(self, status=None):
        return []

    async def open_position(self, **kwargs):
        self.opened.append(kwargs)

        class P:
            id = "p1"

        return P()


def _narrative() -> Narrative:
    return Narrative(
        id="n-live",
        label="FOMO is pumping",
        description="d",
        confidence=0.9,
        cluster_size=25,
        top_tokens=["FOMO"],
        token_mint="MintFOMO111",
    )


def test_signal_engine_routes_to_live_when_on(monkeypatch):
    paper = RecordingEngine()
    live = RecordingEngine()
    eng = SignalEngine(paper, live_trading=live)

    async def fake_price(address):
        return 0.5

    async def fake_gate(address):
        return (True, "ok")

    eng.prices.price_by_address = fake_price
    import app.signals.engine as engine_mod

    monkeypatch.setattr(engine_mod, "safety_gate", fake_gate)
    monkeypatch.setattr(settings, "LIVE_TRADING_ENABLED", False)
    asyncio.run(eng.evaluate(_narrative()))
    assert len(paper.opened) == 1 and not live.opened

    eng.last_trade_at.clear()  # bypass the per-symbol cooldown for run two
    monkeypatch.setattr(settings, "LIVE_TRADING_ENABLED", True)
    asyncio.run(eng.evaluate(_narrative()))
    assert len(live.opened) == 1
