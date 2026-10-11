"""Free, keyless price lookups via DexScreener (Solana-focused)."""
import time
from typing import Optional
import httpx
import structlog


logger = structlog.get_logger()

SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens"


class PriceLookup:
    def __init__(self):
        self._cache: dict[str, tuple[float, dict, float]] = {}  # key -> (price, meta, ts)
        self._ttl = 60.0

    def _cached(self, key: str) -> Optional[tuple[float, dict]]:
        hit = self._cache.get(key)
        if hit and time.time() - hit[2] < self._ttl:
            return hit[0], hit[1]
        return None

    def _store(self, key: str, price: float, meta: dict):
        self._cache[key] = (price, meta, time.time())

    async def resolve_symbol(self, symbol: str) -> Optional[dict]:
        """Find the best Solana pair for a token symbol. Returns {address, symbol, name, price_usd, liquidity_usd}."""
        cached = self._cached(f"sym:{symbol.upper()}")
        if cached:
            price, meta = cached
            return {**meta, "price_usd": price}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(SEARCH_URL, params={"q": symbol})
                resp.raise_for_status()
                pairs = resp.json().get("pairs") or []
        except Exception as e:
            logger.warning("DexScreener search failed", symbol=symbol, error=str(e))
            return None

        sol_pairs = [p for p in pairs if p.get("chainId") == "solana" and p.get("priceUsd")]
        if not sol_pairs:
            return None

        # Prefer the pair with the most liquidity (likely the real token, not an impersonator)
        sol_pairs.sort(key=lambda p: float(p.get("liquidity", {}).get("usd") or 0), reverse=True)
        best = sol_pairs[0]
        base = best.get("baseToken", {})

        try:
            price = float(best["priceUsd"])
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None

        meta = {
            "address": base.get("address", ""),
            "symbol": base.get("symbol", symbol).upper(),
            "name": base.get("name", symbol),
            "liquidity_usd": float(best.get("liquidity", {}).get("usd") or 0),
            "market_cap": best.get("marketCap") or best.get("fdv"),
        }
        self._store(f"sym:{symbol.upper()}", price, meta)
        if meta["address"]:
            self._store(f"addr:{meta['address']}", price, meta)
        return {**meta, "price_usd": price}

    async def price_by_address(self, address: str) -> Optional[float]:
        cached = self._cached(f"addr:{address}")
        if cached:
            return cached[0]

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{TOKENS_URL}/{address}")
                resp.raise_for_status()
                pairs = resp.json().get("pairs") or []
        except Exception as e:
            logger.warning("DexScreener token lookup failed", address=address[:12], error=str(e))
            return None

        sol_pairs = [p for p in pairs if p.get("chainId") == "solana" and p.get("priceUsd")]
        if not sol_pairs:
            return None
        sol_pairs.sort(key=lambda p: float(p.get("liquidity", {}).get("usd") or 0), reverse=True)
        try:
            price = float(sol_pairs[0]["priceUsd"])
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        best = sol_pairs[0]
        self._store(f"addr:{address}", price, {
            "market_cap": best.get("marketCap") or best.get("fdv"),
        })
        return price

    async def market_cap_by_address(self, address: str) -> Optional[float]:
        """Market cap for a mint, from the same DexScreener pair data the
        price lookup already fetches (cached, so usually free)."""
        cached = self._cached(f"addr:{address}")
        if cached and cached[1].get("market_cap"):
            return float(cached[1]["market_cap"])
        if await self.price_by_address(address) is None:
            return None
        cached = self._cached(f"addr:{address}")
        if cached and cached[1].get("market_cap"):
            return float(cached[1]["market_cap"])
        return None
