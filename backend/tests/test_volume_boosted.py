"""Tests for the volume watcher's second feed: DexScreener most-boosted
coins (taking off at any age) and the Mayhem suppression guard."""
import asyncio
import sys
from collections import deque
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.ingestion.volume as volume_mod
from app.ingestion.volume import VolumeWatcher

OLD_HOT = "OldHot1111111111111111111111111111111111"      # not a launch, not pump
MAYHEM = "MayhemCoin111111111111111111111111111pump"      # boosted but Mayhem


class FakePipeline:
    def __init__(self):
        self.narratives = []

    async def emit_narrative(self, narrative):
        self.narratives.append(narrative)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload):
        self._payload = payload

    async def get(self, url, timeout=None, headers=None):
        return FakeResponse(self._payload)


def _watcher(monkeypatch, boosted):
    pipeline = FakePipeline()
    launches = SimpleNamespace(seen_order=deque())
    watcher = VolumeWatcher(pipeline, launches)
    watcher._client = object()

    async def fake_boosted():
        return list(boosted)

    async def fake_stats_batch(mints):
        return {m: {
            "symbol": "HOT", "name": "Hot Coin", "price_usd": "0.1",
            "market_cap": 27_478.0,
            "liquidity_usd": 50_000.0, "volume_h1": 60_000.0,
            "volume_h24": 90_000.0, "buys_h1": 400, "sells_h1": 100,
            "url": "https://dexscreener.com/solana/x",
        } for m in mints}

    monkeypatch.setattr(watcher, "_fetch_boosted_mints", fake_boosted)
    monkeypatch.setattr(watcher, "_fetch_stats_batch", fake_stats_batch)
    return watcher, pipeline


def test_boosted_fetch_filters_solana_and_caps(monkeypatch):
    payload = [
        {"chainId": "solana", "tokenAddress": "A1"},
        {"chainId": "ethereum", "tokenAddress": "0xabc"},
        {"chainId": "solana", "tokenAddress": "A1"},  # duplicate
        {"chainId": "solana", "tokenAddress": "A2"},
    ]
    watcher = VolumeWatcher(FakePipeline(), SimpleNamespace(seen_order=deque()))
    watcher._client = FakeClient(payload)
    monkeypatch.setattr(volume_mod.settings, "VOLUME_BOOST_LIMIT", 2)
    assert asyncio.run(watcher._fetch_boosted_mints()) == ["A1", "A2"]


def test_poll_alerts_on_boosted_coin_of_any_age(monkeypatch):
    async def no_mayhem(mint, client=None):
        return None

    monkeypatch.setattr(volume_mod, "pumpfun_mayhem_state", no_mayhem)
    watcher, pipeline = _watcher(monkeypatch, [OLD_HOT])
    asyncio.run(watcher._poll())
    assert len(pipeline.narratives) == 1
    assert pipeline.narratives[0].token_mint == OLD_HOT
    assert watcher.get_status()["boosted_watched"] == 1


def test_poll_suppresses_boosted_mayhem_coin(monkeypatch):
    async def mayhem(mint, client=None):
        return "active" if mint == MAYHEM else None

    monkeypatch.setattr(volume_mod, "pumpfun_mayhem_state", mayhem)
    watcher, pipeline = _watcher(monkeypatch, [MAYHEM])
    asyncio.run(watcher._poll())
    assert pipeline.narratives == []
    assert watcher.alert_count == 0
