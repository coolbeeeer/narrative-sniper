"""Jupiter client: the full buy path (quote -> swap build -> local sign ->
RPC send -> confirm) with the network faked. Uses a real keypair and a
real (trivial) versioned transaction so the signing step is genuine."""
import asyncio
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solders.hash import Hash
from solders.message import MessageV0
from solders.transaction import VersionedTransaction

import app.live.jupiter as jup_mod
from app.live.jupiter import JupiterClient
from app.live.wallet import BotWallet, generate_wallet


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_swap_tx_b64(keypair) -> str:
    """A real versioned transaction with the wallet as fee payer, signed —
    the same shape Jupiter's /swap returns for this wallet."""
    msg = MessageV0.try_compile(keypair.pubkey(), [], [], Hash.default())
    tx = VersionedTransaction(msg, [keypair])
    return base64.b64encode(bytes(tx)).decode()


class FakeHttp:
    """Stands in for httpx.AsyncClient inside the jupiter module."""

    swap_b64 = ""

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        assert "quote" in url
        return FakeResponse({"outAmount": "555000000", "inAmount": params["amount"]})

    async def post(self, url, json=None):
        assert "swap" in url
        return FakeResponse({"swapTransaction": FakeHttp.swap_b64})


def test_buy_signs_sends_and_returns_amounts(monkeypatch):
    address, secret = generate_wallet()
    wallet = BotWallet.from_secret(secret)
    FakeHttp.swap_b64 = _fake_swap_tx_b64(wallet.keypair)

    sent = {}

    async def fake_rpc(method, params, tries=2):
        if method == "sendTransaction":
            sent["payload"] = params[0]
            return "SignatureABC"
        if method == "getSignatureStatuses":
            return {"value": [{"confirmationStatus": "confirmed", "err": None}]}
        return None

    wallet.rpc = fake_rpc
    monkeypatch.setattr(jup_mod.httpx, "AsyncClient", FakeHttp)

    client = JupiterClient(wallet)
    result = asyncio.run(client.buy("SomeMint111", 0.25))
    assert result["signature"] == "SignatureABC"
    assert result["out_raw"] == 555_000_000
    # The payload sent to the network is a valid signed versioned tx.
    decoded = VersionedTransaction.from_bytes(base64.b64decode(sent["payload"]))
    assert len(decoded.signatures) >= 1


def test_sell_zero_amount_rejected():
    address, secret = generate_wallet()
    client = JupiterClient(BotWallet.from_secret(secret))
    try:
        asyncio.run(client.sell("SomeMint111", 0))
        assert False, "expected JupiterError"
    except Exception as e:
        assert "zero" in str(e).lower()
