"""Tests for the volume watcher (app/ingestion/volume.py): spike detection
thresholds, DexScreener payload parsing, and per-token alert cooldown."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.ingestion.volume import VolumeWatcher, is_spike, parse_pair_stats


def _stats(buys=200, volume=50_000.0):
    return {"buys_h1": buys, "volume_h1": volume}


def test_spike_first_sighting_hot_token():
    # No previous reading: absolute thresholds alone decide.
    assert is_spike(None, _stats()) is True


def test_spike_requires_min_buys():
    assert is_spike(None, _stats(buys=settings.VOLUME_MIN_BUYS_H1 - 1)) is False


def test_spike_requires_min_volume():
    assert is_spike(None, _stats(volume=settings.VOLUME_MIN_VOLUME_H1_USD - 1)) is False


def test_spike_requires_multiple_over_previous():
    prev = 20_000.0
    # 50k is above the absolute floor but only 2.5x the previous reading.
    assert is_spike(prev, _stats(volume=50_000.0)) is False
    # 3x the previous reading clears the bar.
    assert is_spike(prev, _stats(volume=prev * settings.VOLUME_SPIKE_MULTIPLE)) is True


def test_spike_ignores_zero_previous():
    assert is_spike(0.0, _stats()) is True


def _pair(chain="solana", liq=80_000, vol_h1=42_000, buys=321, sells=120):
    return {
        "chainId": chain,
        "baseToken": {"symbol": "FOMO", "name": "Fomo Coin"},
        "priceUsd": "0.0123",
        "liquidity": {"usd": liq},
        "volume": {"h1": vol_h1, "h24": 300_000},
        "txns": {"h1": {"buys": buys, "sells": sells}},
        "url": "https://dexscreener.com/solana/pair",
    }


def test_parse_picks_most_liquid_solana_pair():
    payload = {"pairs": [_pair(liq=10_000, buys=5), _pair(chain="ethereum", liq=999_999), _pair(liq=80_000)]}
    stats = parse_pair_stats(payload)
    assert stats["symbol"] == "FOMO"
    assert stats["buys_h1"] == 321
    assert stats["volume_h1"] == 42_000
    assert stats["liquidity_usd"] == 80_000


def test_parse_no_solana_pair_returns_none():
    assert parse_pair_stats({"pairs": [_pair(chain="ethereum")]}) is None
    assert parse_pair_stats({"pairs": []}) is None
    assert parse_pair_stats(None) is None
    assert parse_pair_stats([]) is None


def test_parse_accepts_bare_list_payload():
    stats = parse_pair_stats([_pair()])
    assert stats is not None and stats["symbol"] == "FOMO"


def test_cooldown_blocks_then_expires():
    watcher = VolumeWatcher(pipeline=None, launch_ingestion=None)
    mint = "Mint111"
    assert watcher._in_cooldown(mint) is False
    watcher.alerted_at[mint] = datetime.now(timezone.utc)
    assert watcher._in_cooldown(mint) is True
    watcher.alerted_at[mint] = datetime.now(timezone.utc) - timedelta(
        hours=settings.VOLUME_COOLDOWN_HOURS + 1
    )
    assert watcher._in_cooldown(mint) is False
