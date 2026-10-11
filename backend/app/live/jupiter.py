"""Jupiter swap client (free lite-api tier, keyless).

Flow for both buys and sells:
  1. GET  /swap/v1/quote        — priced route for an exact input amount
  2. POST /swap/v1/swap         — Jupiter builds the transaction
  3. sign locally with the bot wallet, send via Solana RPC, confirm

Wrapped SOL is the spending currency; buys are SOL -> token and sells are
token -> SOL, with wrapAndUnwrapSol so the wallet only ever holds SOL.
"""
import asyncio
import base64
import time
from typing import Optional

import httpx
import structlog
from solders.transaction import VersionedTransaction

from app.core.config import settings
from app.live.wallet import BotWallet


logger = structlog.get_logger()

JUP_SWAP_BASE = "https://lite-api.jup.ag/swap/v1"
JUP_PRICE_URL = "https://lite-api.jup.ag/price/v3"
WSOL = "So11111111111111111111111111111111111111112"
CONFIRM_TIMEOUT_SECONDS = 90


class JupiterError(RuntimeError):
    pass


class JupiterClient:
    def __init__(self, wallet: BotWallet):
        self.wallet = wallet
        self._sol_price: tuple[float, float] = (0.0, 0.0)  # (price, fetched_at)

    # ---- pricing ----

    async def sol_price_usd(self) -> float:
        price, at = self._sol_price
        if price and time.time() - at < 30:
            return price
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(JUP_PRICE_URL, params={"ids": WSOL})
            r.raise_for_status()
            data = r.json()
        usd = (data.get(WSOL) or {}).get("usdPrice")
        if not usd:
            raise JupiterError("Could not fetch the SOL price from Jupiter")
        self._sol_price = (float(usd), time.time())
        return float(usd)

    # ---- quote + swap ----

    async def _quote(self, client: httpx.AsyncClient, input_mint: str, output_mint: str,
                     amount_raw: int, slippage_bps: int) -> dict:
        r = await client.get(f"{JUP_SWAP_BASE}/quote", params={
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_raw),
            "slippageBps": str(slippage_bps),
        })
        r.raise_for_status()
        return r.json()

    async def _execute(self, quote: dict) -> str:
        """Build, sign, send and confirm a swap for a quote. Returns the
        transaction signature."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{JUP_SWAP_BASE}/swap", json={
                "quoteResponse": quote,
                "userPublicKey": self.wallet.address,
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
            })
            r.raise_for_status()
            swap_tx = (r.json() or {}).get("swapTransaction")
        if not swap_tx:
            raise JupiterError("Jupiter did not return a swap transaction")

        tx = VersionedTransaction.from_bytes(base64.b64decode(swap_tx))
        signed = VersionedTransaction(tx.message, [self.wallet.keypair])
        payload = base64.b64encode(bytes(signed)).decode()
        result = await self.wallet.rpc("sendTransaction", [
            payload, {"encoding": "base64", "maxRetries": 3},
        ])
        if not result:
            raise JupiterError("The network did not accept the swap transaction")
        signature = result
        await self._confirm(signature)
        return signature

    async def _confirm(self, signature: str):
        deadline = time.time() + CONFIRM_TIMEOUT_SECONDS
        while time.time() < deadline:
            result = await self.wallet.rpc("getSignatureStatuses", [[signature]])
            values = (result or {}).get("value") or []
            status = values[0] if values else None
            if status:
                if status.get("err"):
                    raise JupiterError(f"Swap failed on-chain: {status['err']}")
                if status.get("confirmationStatus") in ("confirmed", "finalized"):
                    return
            await asyncio.sleep(2)
        raise JupiterError("Swap was sent but not confirmed in time — check the wallet before retrying")

    # ---- public operations ----

    async def buy(self, mint: str, sol_amount: float, slippage_bps: Optional[int] = None) -> dict:
        """Spend SOL on a token. Returns {signature, out_raw, quote}."""
        lamports = int(sol_amount * 1_000_000_000)
        if lamports <= 0:
            raise JupiterError("Buy amount is zero")
        async with httpx.AsyncClient(timeout=20.0) as client:
            quote = await self._quote(client, WSOL, mint, lamports,
                                      slippage_bps or settings.LIVE_SLIPPAGE_BPS)
        signature = await self._execute(quote)
        logger.info("Live buy executed", mint=mint, sol=sol_amount, signature=signature)
        return {"signature": signature, "out_raw": int(quote.get("outAmount") or 0), "quote": quote}

    async def sell(self, mint: str, amount_raw: int, slippage_bps: Optional[int] = None) -> dict:
        """Sell a raw token amount back to SOL. Returns {signature, out_lamports, quote}."""
        if amount_raw <= 0:
            raise JupiterError("Sell amount is zero")
        async with httpx.AsyncClient(timeout=20.0) as client:
            quote = await self._quote(client, mint, WSOL, amount_raw,
                                      slippage_bps or settings.LIVE_SLIPPAGE_BPS)
        signature = await self._execute(quote)
        logger.info("Live sell executed", mint=mint, amount_raw=amount_raw, signature=signature)
        return {"signature": signature, "out_lamports": int(quote.get("outAmount") or 0), "quote": quote}
