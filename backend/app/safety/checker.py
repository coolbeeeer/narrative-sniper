"""Async token safety (rug) checker for Narrative Sniper.

Ports the proven RugRadar scoring logic (DexScreener + Solana RPC + RugCheck
public API, all keyless except an optional Helius RPC key) into an async
module the signal engine can call as a pre-trade gate.

Scores 0-100 (higher = riskier). Verdicts: SAFE / CAUTION / AVOID.
"""
import asyncio
import time
from typing import Optional

import httpx
import structlog

from app.core.config import settings


logger = structlog.get_logger()

DEXSCREENER_URL = "https://api.dexscreener.com/tokens/v1/solana/{}"
RUGCHECK_REPORT_URL = "https://api.rugcheck.xyz/v1/tokens/{}/report"
RUGCHECK_NEW_TOKENS_URL = "https://api.rugcheck.xyz/v1/stats/new_tokens"

LEGACY_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

# Established tokens: skip deep scoring, they keep authorities by design.
WHITELIST = {
    "So11111111111111111111111111111111111111112": "Wrapped SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USD Coin",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "Tether USD",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "dogwifhat",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "Jupiter",
    "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": "Raydium",
}

WEIGHTS = {
    "mint_authority_not_renounced": 25,
    "freeze_authority_not_renounced": 20,
    "holder_concentration": "0-20 (top10% / 5)",
    "low_liquidity": 15,          # liquidity < SAFETY_MIN_LIQUIDITY_USD
    "no_liquidity_data": 10,
    "lp_not_locked": 10,          # LP locked < 50% when verifiable
    "rugcheck_risk_flag": "5 each, cap 15",
    "insider_network": 20,        # bundled / insider wallets detected
    "low_volume": 10,             # 24h volume < SAFETY_MIN_VOLUME_H24_USD
    "token_age_lt_24h": 10,
    "token_age_lt_7d": 5,
    "transfer_fee": 15,
}

# RugCheck risk score >= this forces a hard block (fail closed).
# RugCheck scores run ~0-10000+; 4500+ is firmly in dangerous territory.
RUGCHECK_HARD_BLOCK_SCORE = 4000


def _rpc_urls() -> list[str]:
    urls: list[str] = []
    if settings.HELIUS_API_KEY:
        urls.append(f"https://mainnet.helius-rpc.com/?api-key={settings.HELIUS_API_KEY}")
    urls += ["https://solana-rpc.publicnode.com", "https://api.mainnet-beta.solana.com"]
    return urls


async def _get_json(client: httpx.AsyncClient, url: str, timeout: float = 20.0) -> Optional[dict | list]:
    try:
        r = await client.get(url, timeout=timeout, headers={"User-Agent": "narrative-sniper/1.0"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.debug("HTTP GET failed", url=url, error=str(e))
        return None


async def _rpc(client: httpx.AsyncClient, method: str, params: list, tries: int = 2) -> Optional[dict]:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    last_err: Optional[Exception] = None
    for url in _rpc_urls():
        for attempt in range(tries):
            try:
                r = await client.post(url, json=payload, timeout=25.0)
                r.raise_for_status()
                data = r.json()
                if data.get("error"):
                    raise RuntimeError(str(data["error"]))
                return data.get("result")
            except Exception as e:
                last_err = e
                await asyncio.sleep(2 ** attempt)
    logger.debug("RPC failed after retries", method=method, error=str(last_err))
    return None


async def get_mint_info(client: httpx.AsyncClient, mint: str) -> Optional[dict]:
    """Mint/freeze authority, decimals, supply, Token-2022 transfer fee."""
    acct = await _rpc(client, "getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    value = (acct or {}).get("value")
    if not value:
        return None
    data = value.get("data", {})
    if data.get("program") not in ("spl-token", "spl-token-2022"):
        return None
    info = data["parsed"]["info"]
    fee_bps = 0
    for ext in info.get("extensions", []) or []:
        if ext.get("extension") == "transferFeeConfig":
            state = ext.get("state", {})
            fee_bps = int(state.get("newerTransferFee", {}).get("transferFeeBasisPoints", 0) or 0)
    return {
        "is_token2022": value.get("owner") != LEGACY_TOKEN_PROGRAM,
        "mint_authority": info.get("mintAuthority"),
        "freeze_authority": info.get("freezeAuthority"),
        "decimals": info.get("decimals"),
        "supply": int(info.get("supply") or 0),
        "transfer_fee_bps": fee_bps,
    }


async def get_dex_pairs(client: httpx.AsyncClient, mint: str) -> Optional[list]:
    data = await _get_json(client, DEXSCREENER_URL.format(mint))
    return data or None


def _best_pair(pairs: list) -> Optional[dict]:
    if not pairs:
        return None
    return max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)


async def get_dex_info(client: httpx.AsyncClient, mint: str) -> Optional[dict]:
    pairs = await get_dex_pairs(client, mint)
    best = _best_pair(pairs or [])
    if not best:
        return None
    liq = (best.get("liquidity") or {}).get("usd") or 0
    created = best.get("pairCreatedAt")
    age_hours = (time.time() * 1000 - created) / 3_600_000 if created else None
    vol = best.get("volume") or {}
    return {
        "name": (best.get("baseToken") or {}).get("name"),
        "symbol": (best.get("baseToken") or {}).get("symbol"),
        "price_usd": best.get("priceUsd"),
        "liquidity_usd": liq,
        "volume_h24_usd": vol.get("h24") or 0,
        "volume_h6_usd": vol.get("h6") or 0,
        "txns_h24": (best.get("txns") or {}).get("h24"),
        "age_hours": age_hours,
        "dex": best.get("dexId"),
        "pair_url": best.get("url"),
    }


async def get_holder_concentration(
    client: httpx.AsyncClient, mint: str, supply: int, rc: Optional[dict]
) -> Optional[float]:
    """Top-10 holder share of total supply (0-100). None if it couldn't run."""
    top_holders = (rc or {}).get("topHolders") or []
    if top_holders:
        return round(sum(h.get("pct", 0) for h in top_holders[:10]), 2)
    res = await _rpc(client, "getTokenLargestAccounts", [mint])
    accounts = (res or {}).get("value") or []
    if not accounts or not supply:
        return None
    top10 = sum(int(a.get("amount", 0)) for a in accounts[:10])
    return round(100.0 * top10 / supply, 2)


async def get_rugcheck_report(client: httpx.AsyncClient, mint: str) -> Optional[dict]:
    data = await _get_json(client, RUGCHECK_REPORT_URL.format(mint), timeout=25.0)
    return data if isinstance(data, dict) and "error" not in data else None


def _lp_locked_pct(rc: Optional[dict]) -> Optional[float]:
    if not rc:
        return None
    if rc.get("lpLockedPct") is not None:
        return float(rc["lpLockedPct"])
    # Fallback: derive from lockers list when present
    lockers = rc.get("lockers") or {}
    if isinstance(lockers, dict) and lockers:
        pcts = [v.get("pct") for v in lockers.values() if isinstance(v, dict) and v.get("pct") is not None]
        if pcts:
            return round(sum(pcts) / len(pcts), 2)
    return None


async def check_token(mint: str, client: Optional[httpx.AsyncClient] = None) -> dict:
    """Run all checks, return score/verdict/findings plus raw metrics."""
    if mint in WHITELIST:
        return {
            "mint": mint,
            "name": WHITELIST[mint],
            "whitelisted": True,
            "score": 5,
            "verdict": "SAFE",
            "findings": [("ok", f"Established token ({WHITELIST[mint]})")],
            "liquidity_usd": None,
            "volume_h24_usd": None,
            "holder_concentration_pct": None,
            "bottom_line": "Well-known token. Normal market risk still applies.",
        }

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()
    assert client is not None

    try:
        mint_info, pairs, rc = await asyncio.gather(
            get_mint_info(client, mint),
            get_dex_pairs(client, mint),
            get_rugcheck_report(client, mint),
        )
        dex = None
        if pairs:
            best = _best_pair(pairs)
            if best:
                # reuse the parsing without a second HTTP call
                liq = (best.get("liquidity") or {}).get("usd") or 0
                created = best.get("pairCreatedAt")
                vol = best.get("volume") or {}
                dex = {
                    "name": (best.get("baseToken") or {}).get("name"),
                    "symbol": (best.get("baseToken") or {}).get("symbol"),
                    "price_usd": best.get("priceUsd"),
                    "liquidity_usd": liq,
                    "volume_h24_usd": vol.get("h24") or 0,
                    "volume_h6_usd": vol.get("h6") or 0,
                    "txns_h24": (best.get("txns") or {}).get("h24"),
                    "age_hours": (time.time() * 1000 - created) / 3_600_000 if created else None,
                    "dex": best.get("dexId"),
                    "pair_url": best.get("url"),
                }

        score = 0.0
        findings: list[tuple[str, str]] = []
        block_reasons: list[str] = []  # hard blocks: fail closed, force AVOID

        # --- mint authority ---
        if mint_info is None:
            # RugCheck report also carries authorities; use as fallback
            rc_mint_auth = (rc or {}).get("mintAuthority")
            if rc_mint_auth:
                score += WEIGHTS["mint_authority_not_renounced"]
                findings.append(("bad", "Mint authority NOT renounced (per RugCheck) — dev can print more tokens"))
                block_reasons.append("mint authority not renounced")
            elif rc and rc_mint_auth == "":
                findings.append(("ok", "Mint authority renounced (per RugCheck)"))
            else:
                score += 40
                findings.append(("bad", "Couldn't verify mint authority — failing closed"))
                block_reasons.append("mint authority unverifiable")
        elif mint_info["mint_authority"] is None:
            findings.append(("ok", "Mint authority renounced — no new tokens can be printed"))
        else:
            score += WEIGHTS["mint_authority_not_renounced"]
            findings.append(("bad", "Mint authority NOT renounced — dev can print more tokens"))
            block_reasons.append("mint authority not renounced")

        # --- freeze authority ---
        if mint_info is None:
            rc_freeze_auth = (rc or {}).get("freezeAuthority")
            if rc_freeze_auth:
                score += WEIGHTS["freeze_authority_not_renounced"]
                findings.append(("bad", "Freeze authority NOT renounced (per RugCheck) — dev can freeze your tokens"))
                block_reasons.append("freeze authority not renounced")
            elif rc and rc_freeze_auth == "":
                findings.append(("ok", "Freeze authority renounced (per RugCheck)"))
            else:
                score += 40
                findings.append(("bad", "Couldn't verify freeze authority — failing closed"))
                block_reasons.append("freeze authority unverifiable")
        elif mint_info["freeze_authority"] is None:
            findings.append(("ok", "Freeze authority renounced — funds can't be frozen"))
        else:
            score += WEIGHTS["freeze_authority_not_renounced"]
            findings.append(("bad", "Freeze authority NOT renounced — dev can freeze your tokens"))
            block_reasons.append("freeze authority not renounced")

        # --- holder concentration ---
        conc = await get_holder_concentration(client, mint, (mint_info or {}).get("supply") or 0, rc)
        if conc is None:
            findings.append(("info", "Couldn't verify holder concentration"))
        else:
            score += min(20.0, conc / 5)
            if conc >= 50:
                findings.append(("bad", f"Top 10 holders own {conc}% — whale-controlled"))
            elif conc >= 25:
                findings.append(("warn", f"Top 10 holders own {conc}% — fairly concentrated"))
            else:
                findings.append(("ok", f"Top 10 holders own {conc}% — reasonably distributed"))

        # --- liquidity ---
        liq = (dex or {}).get("liquidity_usd") or 0
        if dex is None:
            score += 40
            findings.append(("bad", "No trading pair found — can't verify liquidity — failing closed"))
            block_reasons.append("no trading pair / liquidity unverifiable")
        elif liq < settings.SAFETY_MIN_LIQUIDITY_USD:
            score += WEIGHTS["low_liquidity"]
            findings.append(("bad", f"Liquidity only ${liq:,.0f} — easy to drain — blocked"))
            block_reasons.append(f"liquidity ${liq:,.0f} below minimum ${settings.SAFETY_MIN_LIQUIDITY_USD:,.0f}")
        else:
            findings.append(("ok", f"Liquidity ${liq:,.0f} on {dex.get('dex')}"))

        # --- volume ---
        vol24 = (dex or {}).get("volume_h24_usd") or 0
        if dex is None:
            findings.append(("bad", "Couldn't verify trading volume — failing closed"))
            if "no trading pair / liquidity unverifiable" not in block_reasons:
                block_reasons.append("volume unverifiable")
        elif vol24 < settings.SAFETY_MIN_VOLUME_H24_USD:
            score += WEIGHTS["low_volume"]
            findings.append(("bad", f"24h volume only ${vol24:,.0f} — thin market, hard to exit — blocked"))
            block_reasons.append(f"24h volume ${vol24:,.0f} below minimum ${settings.SAFETY_MIN_VOLUME_H24_USD:,.0f}")
        else:
            findings.append(("ok", f"24h volume ${vol24:,.0f}"))

        # --- LP lock ---
        locked = _lp_locked_pct(rc)
        if locked is not None:
            if locked < 50:
                score += WEIGHTS["lp_not_locked"]
                findings.append(("bad", f"Only {locked:.0f}% of LP locked — dev can pull it"))
            else:
                findings.append(("ok", f"{locked:.0f}% of LP locked"))
        else:
            findings.append(("info", "LP lock status: couldn't verify"))

        # --- insider / bundle networks (RugCheck graph analysis) ---
        insiders = (rc or {}).get("graphInsidersDetected") or (rc or {}).get("insiderNetworks")
        if insiders:
            n = len(insiders) if isinstance(insiders, (list, dict)) else 1
            score += WEIGHTS["insider_network"]
            findings.append(("bad", f"Bundled/insider wallet network detected ({n} cluster(s)) — coordinated dump risk"))
            block_reasons.append("insider/bundle network detected")

        # --- RugCheck risk flags ---
        if rc:
            risks = rc.get("risks") or []
            if risks:
                score += min(15, 5 * len(risks))
                for risk in risks[:4]:
                    findings.append(("warn", f"RugCheck flag: {risk.get('name') or risk}"))
            rc_score = rc.get("score") or 0
            if rc_score >= RUGCHECK_HARD_BLOCK_SCORE:
                score = max(score, 90)
                findings.append(("bad", f"RugCheck risk score {rc_score} exceeds block threshold {RUGCHECK_HARD_BLOCK_SCORE} — blocked"))
                block_reasons.append(f"rugcheck score {rc_score} >= {RUGCHECK_HARD_BLOCK_SCORE}")
            if rc.get("rugged"):
                score = max(score, 90)
                findings.append(("bad", "RugCheck marks this token as RUGGED"))
                block_reasons.append("rugged: true")
        else:
            findings.append(("bad", "RugCheck report unavailable — failing closed"))
            block_reasons.append("rugcheck report unavailable")

        # --- token age ---
        age_h = (dex or {}).get("age_hours")
        if age_h is not None:
            if age_h < 24:
                score += WEIGHTS["token_age_lt_24h"]
                findings.append(("warn", f"Token is only {age_h:.0f} hours old"))
            elif age_h < 24 * 7:
                score += WEIGHTS["token_age_lt_7d"]
                findings.append(("warn", f"Token is only {age_h / 24:.0f} days old"))
            else:
                findings.append(("ok", f"Token is {age_h / 24:.0f} days old"))
        else:
            findings.append(("info", "Couldn't verify token age"))

        # --- transfer fee ---
        fee_bps = (mint_info or {}).get("transfer_fee_bps") or 0
        if fee_bps:
            score += WEIGHTS["transfer_fee"]
            findings.append(("bad", f"Hidden transfer tax: {fee_bps / 100:.2f}% on every transfer"))
        else:
            findings.append(("ok", "No hidden transfer tax"))

        score = int(max(0, min(100, round(score))))
        verdict = "SAFE" if score <= 25 else ("CAUTION" if score <= 60 else "AVOID")
        if block_reasons:
            score = 100
            verdict = "AVOID"
        name = (dex or {}).get("name") or (rc or {}).get("tokenMeta", {}).get("name") or "Unknown token"

        if verdict == "AVOID":
            bottom = "High risk of losing your money — skipped by the safety gate."
        elif verdict == "CAUTION":
            bottom = "Some red flags. Trade only with small size and watch it closely."
        else:
            bottom = "No major red flags found. Still do your own research."

        return {
            "mint": mint,
            "name": name,
            "whitelisted": False,
            "score": score,
            "verdict": verdict,
            "block_reasons": block_reasons,
            "findings": findings,
            "liquidity_usd": liq if dex else None,
            "volume_h24_usd": vol24 if dex else None,
            "holder_concentration_pct": conc,
            "dex_url": (dex or {}).get("pair_url"),
            "bottom_line": bottom,
        }
    finally:
        if own_client:
            await client.aclose()


# ---------------------------------------------------------------------------
# Gate helper with short-lived caching (avoids hammering APIs per narrative)
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL_SECONDS = 600


async def safety_gate(mint: str) -> tuple[bool, dict]:
    """Returns (allowed, report). Blocks AVOID verdicts and scores over the limit."""
    now = time.time()
    cached = _cache.get(mint)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        report = cached[1]
    else:
        report = await check_token(mint)
        _cache[mint] = (now, report)
        # keep cache bounded
        if len(_cache) > 500:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            del _cache[oldest]

    if not settings.SAFETY_ENABLED:
        return True, report
    if report["verdict"] == "AVOID" or report["score"] > settings.SAFETY_MAX_RISK_SCORE:
        return False, report
    return True, report


def clear_cache() -> None:
    _cache.clear()
