"""Tests for the widened watch window (batched stats), the early-warning
tier, and market-cap-at-catch recording."""
import asyncio
import sys
from collections import deque
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.ingestion.volume as volume_mod
from app.core.config import settings
from app.ingestion.volume import VolumeWatcher, is_spike, parse_pair_stats

MINT_A = "MintA111111111111111111111111111111111111"
MINT_B = "MintB222222222222222222222222222222222222"


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
        self.urls = []

    async def get(self, url, timeout=None, headers=None):
        self.urls.append(url)
        return FakeResponse(self._payload)


def _pair(mint, symbol, mc, liq=60_000.0, vol_h1=50_000.0, buys=300):
    return {
        "chainId": "solana",
        "baseToken": {"address": mint, "symbol": symbol, "name": f"{symbol} Coin"},
        "priceUsd": "0.001",
        "marketCap": mc,
        "liquidity": {"usd": liq},
        "volume": {"h1": vol_h1, "h24": vol_h1 * 2},
        "txns": {"h1": {"buys": buys, "sells": 10}},
        "url": "https://dexscreener.com/solana/x",
    }


def test_parse_pair_stats_carries_market_cap():
    stats = parse_pair_stats([_pair(MINT_A, "AAA", 12_345.0)])
    assert stats["market_cap"] == 12_345.0


def test_batch_fetch_groups_pairs_by_mint():
    payload = [_pair(MINT_A, "AAA", 10_000.0), _pair(MINT_B, "BBB", 20_000.0)]
    watcher = VolumeWatcher(FakePipeline(), SimpleNamespace(seen_order=deque()))
    client = FakeClient(payload)
    watcher._client = client
    out = asyncio.run(watcher._fetch_stats_batch([MINT_A, MINT_B]))
    assert out[MINT_A]["symbol"] == "AAA"
    assert out[MINT_B]["market_cap"] == 20_000.0
    # Both mints went in ONE batched request.
    assert len(client.urls) == 1
    assert f"{MINT_A},{MINT_B}" in client.urls[0]


def test_early_tier_thresholds():
    stats = {"buys_h1": settings.VOLUME_EARLY_MIN_BUYS_H1,
             "volume_h1": settings.VOLUME_EARLY_MIN_VOLUME_H1_USD}
    # Clears the early floors but not the full-surge floors.
    assert is_spike(None, stats,
                    min_buys=settings.VOLUME_EARLY_MIN_BUYS_H1,
                    min_volume=settings.VOLUME_EARLY_MIN_VOLUME_H1_USD) is True
    assert is_spike(None, stats) is False


def _poll_with_stats(monkeypatch, stats):
    pipeline = FakePipeline()
    launches = SimpleNamespace(seen_order=deque([MINT_A]))
    watcher = VolumeWatcher(pipeline, launches)
    watcher._client = object()

    async def fake_batch(mints):
        return {MINT_A: stats}

    async def fake_boosted():
        return []

    async def no_mayhem(mint, client=None):
        return None

    monkeypatch.setattr(watcher, "_fetch_stats_batch", fake_batch)
    monkeypatch.setattr(watcher, "_fetch_boosted_mints", fake_boosted)
    monkeypatch.setattr(volume_mod, "pumpfun_mayhem_state", no_mayhem)
    asyncio.run(watcher._poll())
    return watcher, pipeline


def test_early_alert_records_market_cap(monkeypatch):
    stats = {
        "symbol": "TINY", "name": "Tiny Coin", "price_usd": "0.000005",
        "market_cap": 5_200.0, "liquidity_usd": 900.0,
        "volume_h1": 3_400.0, "volume_h24": 3_400.0,
        "buys_h1": 80, "sells_h1": 20, "url": "",
    }
    _, pipeline = _poll_with_stats(monkeypatch, stats)
    assert len(pipeline.narratives) == 1
    n = pipeline.narratives[0]
    assert n.label.startswith("Early buying activity")
    assert n.caught_market_cap == 5_200.0
    assert "Caught at $5,200 market cap" in n.description


def test_surge_alert_records_market_cap(monkeypatch):
    stats = {
        "symbol": "BIG", "name": "Big Coin", "price_usd": "0.001",
        "market_cap": 27_478.0, "liquidity_usd": 60_000.0,
        "volume_h1": 33_000.0, "volume_h24": 48_000.0,
        "buys_h1": 287, "sells_h1": 200, "url": "",
    }
    _, pipeline = _poll_with_stats(monkeypatch, stats)
    assert len(pipeline.narratives) == 1
    n = pipeline.narratives[0]
    assert n.label.startswith("Silent buying surge")
    assert n.caught_market_cap == 27_478.0
