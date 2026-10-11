"""Tests for the pump.fun Mayhem Mode coin exclusion:
helper detection, the safety-gate backstop, and the ingestion filter."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.ingestion.launches as launches_mod
import app.safety.checker as checker
from app.ingestion.launches import LaunchIngestion

PUMP_MINT = "AbCdEfGh11111111111111111111111111111pump"
PLAIN_MINT = "SoMeMint1111111111111111111111111111111"


# ---- helper ----

def test_helper_returns_mayhem_state(monkeypatch):
    async def fake_get_json(client, url, timeout=20.0):
        return {"mayhem_state": "active"}

    monkeypatch.setattr(checker, "_get_json", fake_get_json)
    assert asyncio.run(checker.pumpfun_mayhem_state(PUMP_MINT, client=object())) == "active"


def test_helper_normal_coin_returns_none(monkeypatch):
    async def fake_get_json(client, url, timeout=20.0):
        return {"mayhem_state": None}

    monkeypatch.setattr(checker, "_get_json", fake_get_json)
    assert asyncio.run(checker.pumpfun_mayhem_state(PUMP_MINT, client=object())) is None


def test_helper_never_queries_non_pump_mints(monkeypatch):
    called = False

    async def fake_get_json(client, url, timeout=20.0):
        nonlocal called
        called = True
        return {"mayhem_state": "active"}

    monkeypatch.setattr(checker, "_get_json", fake_get_json)
    assert asyncio.run(checker.pumpfun_mayhem_state(PLAIN_MINT, client=object())) is None
    assert called is False


def test_helper_lookup_failure_fails_open(monkeypatch):
    async def fake_get_json(client, url, timeout=20.0):
        return None

    monkeypatch.setattr(checker, "_get_json", fake_get_json)
    assert asyncio.run(checker.pumpfun_mayhem_state(PUMP_MINT, client=object())) is None


# ---- safety gate backstop ----

def test_gate_blocks_mayhem_coin(monkeypatch):
    async def fake_state(mint, client=None):
        return "paused"

    monkeypatch.setattr(checker, "pumpfun_mayhem_state", fake_state)
    allowed, report = asyncio.run(checker.safety_gate(PUMP_MINT))
    assert allowed is False
    assert report["verdict"] == "AVOID"
    assert "Mayhem" in report["bottom_line"]


def test_gate_passes_normal_coin_to_full_check(monkeypatch):
    async def fake_state(mint, client=None):
        return None

    async def fake_check(mint, client=None):
        return {"verdict": "SAFE", "score": 5}

    monkeypatch.setattr(checker, "pumpfun_mayhem_state", fake_state)
    monkeypatch.setattr(checker, "check_token", fake_check)
    checker.clear_cache()
    allowed, _ = asyncio.run(checker.safety_gate(PLAIN_MINT))
    assert allowed is True
    checker.clear_cache()


# ---- ingestion filter ----

class FakePipeline:
    def __init__(self):
        self.items = []

    async def process(self, item):
        self.items.append(item)


def test_ingestion_drops_mayhem_keeps_normal(monkeypatch):
    async def fake_state(mint, client=None):
        return "active" if mint == PUMP_MINT else None

    monkeypatch.setattr(launches_mod, "pumpfun_mayhem_state", fake_state)

    pipeline = FakePipeline()
    ing = LaunchIngestion(pipeline)
    ing._client = object()  # _poll only requires a client to exist

    async def fake_rugcheck():
        return [
            {"mint": PUMP_MINT, "symbol": "MAY", "name": "MayhemCoin", "source": "rugcheck"},
            {"mint": PLAIN_MINT, "symbol": "OK", "name": "NormalCoin", "source": "rugcheck"},
        ]

    async def fake_profiles():
        return []

    monkeypatch.setattr(ing, "_fetch_rugcheck_new", fake_rugcheck)
    monkeypatch.setattr(ing, "_fetch_dexscreener_profiles", fake_profiles)

    asyncio.run(ing._poll())

    processed_mints = [i["token_mint"] for i in pipeline.items]
    assert processed_mints == [PLAIN_MINT]
    assert ing.skipped_mayhem == 1
    assert PUMP_MINT not in ing.seen_order  # volume watcher never tracks it
    assert PLAIN_MINT in ing.seen_order
    assert ing.get_status()["skipped_mayhem"] == 1
