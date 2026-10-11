"""The bot wallet: a dedicated Solana wallet the sniper trades from when
live mode is on.

Custody rules (deliberate, and worth restating):
  - The secret key is read ONLY from settings.BOT_WALLET_PRIVATE_KEY,
    which belongs in the local .env file (gitignored; the repo is public).
  - The secret is never logged, never returned by any API, never written
    anywhere by this code. Only the public address is ever exposed.
  - This wallet is a hot wallet by design: fund it only with what the
    strategy is allowed to lose.

Run directly to generate a fresh wallet:
    python -m app.live.wallet
It prints the new address and secret key ONCE, for the .env file.
"""
import asyncio
from typing import Optional

import httpx
import structlog
from solders.keypair import Keypair

from app.core.config import settings


logger = structlog.get_logger()

LAMPORTS_PER_SOL = 1_000_000_000


def _rpc_urls() -> list[str]:
    urls: list[str] = []
    if settings.HELIUS_API_KEY:
        urls.append(f"https://mainnet.helius-rpc.com/?api-key={settings.HELIUS_API_KEY}")
    if settings.SOLANA_RPC_URL:
        urls.append(settings.SOLANA_RPC_URL)
    urls += ["https://solana-rpc.publicnode.com", "https://api.mainnet-beta.solana.com"]
    # dedupe, keep order
    return list(dict.fromkeys(urls))


class BotWallet:
    def __init__(self, keypair: Keypair):
        self._keypair = keypair

    # ---- construction ----

    @classmethod
    def from_secret(cls, secret: str) -> "BotWallet":
        """Load from a base58 secret key (64-byte full keypair or 32-byte seed)."""
        secret = (secret or "").strip()
        if not secret:
            raise ValueError("BOT_WALLET_PRIVATE_KEY is not set")
        try:
            return cls(Keypair.from_base58_string(secret))
        except Exception:
            pass
        # Some tools export the 32-byte seed only; solders wants the full
        # 64-byte keypair for from_base58_string in that case it still works
        # above — anything else is simply malformed.
        raise ValueError("BOT_WALLET_PRIVATE_KEY is not a valid base58 Solana secret key")

    @classmethod
    def load(cls) -> Optional["BotWallet"]:
        """Wallet from settings, or None when no key is configured.
        A configured-but-malformed key raises (fail loud, never silent)."""
        if not (settings.BOT_WALLET_PRIVATE_KEY or "").strip():
            return None
        return cls.from_secret(settings.BOT_WALLET_PRIVATE_KEY)

    # ---- identity ----

    @property
    def keypair(self) -> Keypair:
        return self._keypair

    @property
    def address(self) -> str:
        return str(self._keypair.pubkey())

    # ---- RPC ----

    async def rpc(self, method: str, params: list, tries: int = 2):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        last_err: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=25.0) as client:
            for url in _rpc_urls():
                for attempt in range(tries):
                    try:
                        r = await client.post(url, json=payload)
                        r.raise_for_status()
                        data = r.json()
                        if data.get("error"):
                            raise RuntimeError(str(data["error"]))
                        return data.get("result")
                    except Exception as e:
                        last_err = e
                        await asyncio.sleep(2 ** attempt)
        logger.warning("Wallet RPC failed", method=method, error=str(last_err))
        return None

    # ---- balances ----

    async def sol_balance(self) -> Optional[float]:
        result = await self.rpc("getBalance", [self.address])
        if not result:
            return None
        return (result.get("value") or 0) / LAMPORTS_PER_SOL

    async def token_balance(self, mint: str) -> Optional[dict]:
        """{raw: int, decimals: int, human: float} for the wallet's holdings
        of one mint, summed across its token accounts. None if RPC failed."""
        result = await self.rpc("getTokenAccountsByOwner", [
            self.address,
            {"mint": mint},
            {"encoding": "jsonParsed"},
        ])
        if result is None:
            return None
        raw = 0
        decimals = 0
        for acct in result.get("value") or []:
            info = (((acct.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
            amount = info.get("tokenAmount") or {}
            raw += int(amount.get("amount") or 0)
            decimals = int(amount.get("decimals") or decimals)
        return {"raw": raw, "decimals": decimals, "human": raw / (10 ** decimals) if decimals else float(raw)}

    async def status(self) -> dict:
        """Public status for the API/dashboard. Never includes the secret."""
        sol = await self.sol_balance()
        return {
            "configured": True,
            "address": self.address,
            "sol_balance": sol,
            "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        }

    @staticmethod
    def unconfigured_status() -> dict:
        return {
            "configured": False,
            "address": None,
            "sol_balance": None,
            "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        }


def generate_wallet() -> tuple[str, str]:
    """(address, base58 secret) for a brand-new wallet."""
    import base58

    kp = Keypair()
    return str(kp.pubkey()), base58.b58encode(bytes(kp)).decode()


if __name__ == "__main__":
    address, secret = generate_wallet()
    print("New bot wallet created.\n")
    print(f"Wallet address (fund this with a small amount of SOL):\n  {address}\n")
    print("Secret key — paste into backend/.env as BOT_WALLET_PRIVATE_KEY:")
    print(f"  {secret}\n")
    print("Keep the secret out of git, chats and screenshots. Anyone with")
    print("it controls the wallet. This is shown once; it is not stored.")
