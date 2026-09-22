"""Tests for the pre-trade safety gate (app/safety/checker.py): scoring,
fail-closed behavior, bundle/insider detection, caching, and gate blocking."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.safety.checker as checker


MINT = "8gD6cTqB2v9xKzN4mP5rS7tU1wY3zA6bC9dE2fG5hJ8k"  # not whitelisted


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


_real_check_token = checker.check_token

async def _check_token_no_net(mint, client=None):
    """check_token with a dummy client: stubs do all the work, no real HTTP."""
    return await _real_check_token(mint, client=object())


def _use_no_net():
    checker.check_token = _check_token_no_net


def _restore():
    checker.check_token = _real_check_token


def _make_stub(*, mint_info, pairs, rc, holders=None):
    async def fake_mint_info(client, mint):
        return mint_info

    async def fake_pairs(client, mint):
        return pairs

    async def fake_rc(client, mint):
        return rc

    async def fake_holders(client, mint, supply, rc):
        # production returns Optional[float]; normalize test fixtures to match
        if isinstance(holders, dict):
            return holders.get("top10_pct")
        return holders

    checker.get_mint_info = fake_mint_info
    checker.get_dex_pairs = fake_pairs
    checker.get_rugcheck_report = fake_rc
    checker.get_holder_concentration = fake_holders
    checker.clear_cache()
    _use_no_net()


def _clean_inputs():
    mint_info = {"mint_authority": None, "freeze_authority": None}
    pairs = [
        {
            "liquidity": {"usd": 150_000.0},
            "volume": {"h24": 80_000.0, "h6": 10_000.0},
            "baseToken": {"name": "Test Token", "symbol": "TEST"},
            "priceUsd": "0.01",
            "pairCreatedAt": None,
            "dexId": "raydium",
            "url": "https://dexscreener.com/solana/x",
            "txns": {"h24": {"buys": 10, "sells": 5}},
        }
    ]
    rc = {"risks": [], "score": 0, "rugged": False}
    holders = {"top10_pct": 12.0}
    return mint_info, pairs, rc, holders


def test_clean_token_scores_low_and_passes_gate():
    mint_info, pairs, rc, holders = _clean_inputs()
    _make_stub(mint_info=mint_info, pairs=pairs, rc=rc, holders=holders)
    report = run(checker.check_token(MINT))
    assert report["verdict"] in ("SAFE", "CAUTION"), report
    allowed, _ = run(checker.safety_gate(MINT))
    assert allowed is True


def test_missing_data_fails_closed():
    _make_stub(mint_info=None, pairs=None, rc=None, holders=None)
    report = run(checker.check_token(MINT))
    assert report["verdict"] == "AVOID", report
    allowed, _ = run(checker.safety_gate(MINT))
    assert allowed is False


def test_mint_authority_not_renounced_penalized():
    mint_info, pairs, rc, holders = _clean_inputs()
    mint_info = {"mint_authority": "SomeDeployerWallet1111111111111111111111", "freeze_authority": None}
    _make_stub(mint_info=mint_info, pairs=pairs, rc=rc, holders=holders)
    report = run(checker.check_token(MINT))
    assert report["score"] > 0
    assert any("mint authority" in f[1].lower() for f in report["findings"])


def test_bundle_or_insider_flags_penalized():
    mint_info, pairs, rc, holders = _clean_inputs()
    rc = {
        "risks": [{"name": "Insider networks detected", "level": "danger"}],
        "score": 1200,
        "rugged": False,
    }
    _make_stub(mint_info=mint_info, pairs=pairs, rc=rc, holders=holders)
    report = run(checker.check_token(MINT))
    text = " ".join(f[1] for f in report["findings"]).lower()
    assert "insider" in text or "bundle" in text
    assert report["score"] > 0


def test_low_liquidity_blocks_gate():
    mint_info, pairs, rc, holders = _clean_inputs()
    pairs[0]["liquidity"] = {"usd": 500.0}
    _make_stub(mint_info=mint_info, pairs=pairs, rc=rc, holders=holders)
    report = run(checker.check_token(MINT))
    allowed, _ = run(checker.safety_gate(MINT))
    assert allowed is False
    assert report["liquidity_usd"] < 20000.0


def test_high_rugcheck_score_blocks_gate():
    mint_info, pairs, rc, holders = _clean_inputs()
    rc = {"risks": [{"name": "Copycat token", "level": "warn"}], "score": 4500, "rugged": False}
    _make_stub(mint_info=mint_info, pairs=pairs, rc=rc, holders=holders)
    report = run(checker.check_token(MINT))
    allowed, _ = run(checker.safety_gate(MINT))
    assert allowed is False


def test_rugged_token_blocked():
    mint_info, pairs, rc, holders = _clean_inputs()
    rc = {"risks": [], "score": 0, "rugged": True}
    _make_stub(mint_info=mint_info, pairs=pairs, rc=rc, holders=holders)
    report = run(checker.check_token(MINT))
    assert report["verdict"] == "AVOID"
    allowed, _ = run(checker.safety_gate(MINT))
    assert allowed is False


def test_gate_cache_serves_second_call_without_refetch():
    mint_info, pairs, rc, holders = _clean_inputs()
    calls = {"n": 0}
    orig = checker.check_token

    async def counting(mint, client=None):
        calls["n"] += 1
        return await orig(mint, client)

    _make_stub(mint_info=mint_info, pairs=pairs, rc=rc, holders=holders)
    checker.check_token = counting
    try:
        run(checker.safety_gate(MINT))
        run(checker.safety_gate(MINT))
    finally:
        _use_no_net()
    assert calls["n"] == 1


def test_whitelisted_tokens_skip_deep_checks():
    # invalid BONK mint must NOT be whitelisted (31 bytes, not a real address)
    assert "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB7" not in checker.WHITELIST
    report = run(checker.check_token("So11111111111111111111111111111111111111112"))
    assert report["verdict"] == "SAFE"
    assert report.get("whitelisted") is True
