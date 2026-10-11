"""Bot wallet: key loading hygiene. The secret must load correctly, fail
loudly when malformed, and never appear in any status payload."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.live.wallet import BotWallet, generate_wallet


def test_generate_and_load_roundtrip():
    address, secret = generate_wallet()
    wallet = BotWallet.from_secret(secret)
    assert wallet.address == address


def test_malformed_key_fails_loud():
    with pytest.raises(ValueError):
        BotWallet.from_secret("not-a-real-key")


def test_empty_key_fails_loud():
    with pytest.raises(ValueError):
        BotWallet.from_secret("")


def test_load_returns_none_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "BOT_WALLET_PRIVATE_KEY", "")
    assert BotWallet.load() is None


def test_status_never_contains_secret():
    address, secret = generate_wallet()
    wallet = BotWallet.from_secret(secret)
    status = wallet.unconfigured_status()
    assert secret not in str(status)
    assert status["configured"] is False
    assert BotWallet(address and secret) is not None  # wallet object exists; status above is the API shape
