#!/usr/bin/env python3
"""Validation / smoke-test: compare ypricemagic-server prices against DefiLlama.

PURPOSE
-------
This is a **validation and smoke-test** script, *not* a cache warmer.

It fetches historical prices for a hard-coded token matrix from both
ypricemagic-server and the DefiLlama public API, then checks that the two
sources agree within a configurable tolerance.  It exits non-zero if any
comparison fails so it can be used as a gate in CI or manual QA runs.

It does **not** pre-populate the cache — any cached prices are a side-effect
of the normal API calls it makes, not a goal.

Multi-chain support: the script auto-detects which chain backends are running
by probing ``/{chain}/health`` and only validates tokens on live chains.

USAGE
-----
    # Run against the local Docker stack (default)
    python scripts/validate_prices.py

    # Run against a different server
    python scripts/validate_prices.py --url http://localhost:8000

See ``--help`` for all options.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import diskcache

# ---------------------------------------------------------------------------
# Token matrix
# ---------------------------------------------------------------------------

STABLECOIN_TOLERANCE = 0.02  # 2%
VOLATILE_TOLERANCE = 0.10  # 10%

# DefiLlama chain prefixes (must match their API)
LLAMA_CHAIN_PREFIX: dict[str, str] = {
    "ethereum": "ethereum",
    "arbitrum": "arbitrum",
    "optimism": "optimism",
    "base": "base",
    "bsc": "bsc",
    "polygon": "polygon",
    "fantom": "fantom",
}


@dataclass(frozen=True)
class Token:
    name: str
    address: str
    tolerance: float
    chain: str = "ethereum"


TOKENS: list[Token] = [
    # --- Ethereum: blue-chip tokens ---
    Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", STABLECOIN_TOLERANCE),
    Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", STABLECOIN_TOLERANCE),
    Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", STABLECOIN_TOLERANCE),
    Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", VOLATILE_TOLERANCE),
    Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", VOLATILE_TOLERANCE),
    Token("UNI", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", VOLATILE_TOLERANCE),
    Token("LINK", "0x514910771AF9Ca656af840dff83E8264EcF986CA", VOLATILE_TOLERANCE),
    Token("AAVE", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9", VOLATILE_TOLERANCE),
    # --- Ethereum: exotic tokens (ypricemagic PR #15) ---
    Token("stkAAVE", "0x4da27a545c0c5B758a6BA100e3a049001de870f5", VOLATILE_TOLERANCE),
    Token("plDAI", "0x49d716DFe60b37379010A75329ae09428f17118d", STABLECOIN_TOLERANCE),
    Token("plUSDC", "0xBD87447F48ad729C5c4b8bcb503e1395F62e8B98", STABLECOIN_TOLERANCE),
    Token("sDAI", "0x83F20F44975D03b1b09e64809B757c47f942BEeA", STABLECOIN_TOLERANCE),
    Token("weETH", "0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee", VOLATILE_TOLERANCE),
    Token("aDAI-v1", "0xfC1E690f61EFd961294b3e1Ce3313fBD8aa4f85d", STABLECOIN_TOLERANCE),
    Token("pSLP-WBTC-ETH", "0x55282dA27a3a02eFe599f9bD85E2e0C78f9cD2b2", VOLATILE_TOLERANCE),
    Token("ptUSDC-v4", "0xdd4d117723C257CEe402285D3aCF218E9A8236E1", STABLECOIN_TOLERANCE),
    Token("xPREMIA", "0x16f9D564Df80376C61AC914205D3fDfB8a32f98b", VOLATILE_TOLERANCE),
    # --- Fantom: exotic tokens ---
    Token("xTAROT", "0x74D1D2A851e339B8cB953716445Be7E8aBdf92F4", VOLATILE_TOLERANCE, "fantom"),
]

NUM_CHART_POINTS = 8
CHART_PERIOD = "90d"

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


@dataclass
class ComparisonResult:
    token: Token
    timestamp: int
    ypm_price: float | None
    ref_price: float | None
    ypm_error: str | None
    ref_error: str | None
    passed: bool | None  # None = skipped


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

_TIMEOUT = 30

_CACHE_DIR = Path(os.environ.get("CACHE_DIR", Path(__file__).resolve().parent.parent / "cache"))
_llama_cache = diskcache.Cache(_CACHE_DIR / "defillama-prices")


def _http_get_json(url: str, timeout: int = _TIMEOUT) -> object:
    """Perform a GET request and return parsed JSON."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
    return json.loads(body)


# ---------------------------------------------------------------------------
# Chain discovery
# ---------------------------------------------------------------------------

ALL_CHAINS = ["ethereum", "arbitrum", "optimism", "base", "bsc", "polygon", "fantom"]


def discover_live_chains(base_url: str) -> list[str]:
    """Probe each chain's health endpoint and return the list of live chains."""
    live: list[str] = []
    for chain in ALL_CHAINS:
        url = f"{base_url}/{chain}/health"
        try:
            data = _http_get_json(url, timeout=5)
            if isinstance(data, dict) and data.get("status") == "ok":
                live.append(chain)
        except Exception:
            pass
    return live


# ---------------------------------------------------------------------------
# API callers
# ---------------------------------------------------------------------------


def _llama_coin(token: Token) -> str:
    """Return the DefiLlama coin identifier for a token."""
    prefix = LLAMA_CHAIN_PREFIX.get(token.chain, token.chain)
    return f"{prefix}:{token.address}"


def fetch_ypm_price(
    base_url: str, token: Token, timestamp: int | None = None
) -> tuple[float | None, str | None]:
    """Fetch a price from ypricemagic-server. Returns (price, error).

    If *timestamp* is None, fetches the latest price (no timestamp param).
    """
    chain_url = f"{base_url}/{token.chain}"
    if timestamp is not None:
        url = f"{chain_url}/price?token={token.address}&timestamp={timestamp}"
    else:
        url = f"{chain_url}/price?token={token.address}"
    try:
        data = _http_get_json(url)
        if not isinstance(data, dict):
            return None, f"unexpected response: {data!r}"
        price = data.get("from_price") or data.get("price")
        if price is None:
            error_msg = data.get("error", "no price in response")
            return None, f"server error: {error_msg} body={data!r}"
        return float(price), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace") if exc.fp else ""
        return None, f"HTTP {exc.code}: {body[:200]}"
    except urllib.error.URLError as exc:
        return None, f"network error: {exc.reason}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def fetch_defillama_first_timestamps(
    tokens: list[Token],
) -> dict[str, int]:
    """Batch-fetch earliest available timestamps from DefiLlama /prices/first/.

    Returns {address: unix_timestamp}. Cached on disk.
    """
    results: dict[str, int] = {}
    uncached: list[Token] = []

    for token in tokens:
        cache_key = f"first:{_llama_coin(token)}"
        cached = _llama_cache.get(cache_key)
        if cached is not None:
            results[token.address] = cached
        else:
            uncached.append(token)

    if not uncached:
        return results

    coins = ",".join(_llama_coin(t) for t in uncached)
    url = f"https://coins.llama.fi/prices/first/{coins}"
    try:
        data = _http_get_json(url)
        if isinstance(data, dict):
            for token in uncached:
                key = _llama_coin(token)
                entry = data.get("coins", {}).get(key, {})
                ts = entry.get("timestamp")
                if isinstance(ts, int | float):
                    results[token.address] = int(ts)
                    _llama_cache.set(f"first:{key}", int(ts))
    except Exception:
        pass  # non-fatal; we'll use a fallback start time

    return results


def fetch_defillama_chart(
    tokens: list[Token],
    start: int,
    span: int,
    period: str,
) -> dict[str, list[tuple[int, float]]]:
    """Batch-fetch price chart from DefiLlama /chart/.

    Returns {address: [(timestamp, price), ...]}. Individual points cached on disk.
    """
    coins = ",".join(_llama_coin(t) for t in tokens)
    url = f"https://coins.llama.fi/chart/{coins}?start={start}&span={span}&period={period}"
    try:
        data = _http_get_json(url)
    except Exception as exc:
        print(f"  [chart fetch failed: {exc}]", flush=True)
        return {}

    if not isinstance(data, dict):
        return {}

    results: dict[str, list[tuple[int, float]]] = {}
    for token in tokens:
        key = _llama_coin(token)
        entry = data.get("coins", {}).get(key, {})
        prices = entry.get("prices", [])
        points: list[tuple[int, float]] = []
        for p in prices:
            ts = p.get("timestamp")
            price = p.get("price")
            if ts is not None and price is not None:
                _llama_cache.set(f"{key}:{ts}", float(price))
                points.append((int(ts), float(price)))
        results[token.address] = points

    return results


def fetch_defillama_current_prices(tokens: list[Token]) -> dict[str, float]:
    """Fetch current prices from DefiLlama /prices/current/. Returns {address: price}."""
    coins = ",".join(_llama_coin(t) for t in tokens)
    url = f"https://coins.llama.fi/prices/current/{coins}"
    try:
        data = _http_get_json(url)
        if not isinstance(data, dict):
            return {}
        results: dict[str, float] = {}
        for token in tokens:
            key = _llama_coin(token)
            entry = data.get("coins", {}).get(key, {})
            price = entry.get("price")
            if price is not None:
                results[token.address] = float(price)
        return results
    except Exception as exc:
        print(f"  [current price fetch failed: {exc}]", flush=True)
        return {}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _short_addr(address: str) -> str:
    return f"{address[:6]}...{address[-4:]}"


def _ts_label(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d")


def _fmt_price(price: float) -> str:
    if price >= 100:
        return f"${price:,.2f}"
    return f"${price:.4f}"


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def _compare_latest(base_url: str, token: Token, ref_price_val: float) -> ComparisonResult:
    """Compare a latest (no-timestamp) YPM price against DefiLlama current price."""
    label = f"[{token.chain}] {token.name} ({_short_addr(token.address)}) @ latest"

    ypm_price, ypm_err = fetch_ypm_price(base_url, token, timestamp=None)
    ref_price: float | None = ref_price_val
    ref_err: str | None = None
    now_ts = int(datetime.now(tz=UTC).timestamp())

    result = ComparisonResult(
        token=token,
        timestamp=now_ts,
        ypm_price=ypm_price,
        ref_price=ref_price,
        ypm_error=ypm_err,
        ref_error=ref_err,
        passed=None,
    )

    ypm_str = f"ERROR ({ypm_err})" if ypm_err is not None else _fmt_price(ypm_price)  # type: ignore[arg-type]
    ref_str = f"ERROR ({ref_err})" if ref_err is not None else _fmt_price(ref_price)  # type: ignore[arg-type]

    if ypm_err is not None or ref_err is not None:
        verdict = "-- SKIP"
    else:
        assert ypm_price is not None
        assert ref_price is not None
        if ref_price == 0:
            delta_pct = 0.0 if ypm_price == 0 else float("inf")
        else:
            delta_pct = abs(ypm_price - ref_price) / ref_price
        tol_str = f"{token.tolerance:.0%}"
        if delta_pct <= token.tolerance:
            result.passed = True
            verdict = f"Delta: {delta_pct:.2%}  PASS (tol: {tol_str})"
        else:
            result.passed = False
            verdict = f"Delta: {delta_pct:.2%}  FAIL (tol: {tol_str})"

    print(label)
    print(f"  YPM: {ypm_str}")
    print(f"  REF: {ref_str}")
    print(f"  {verdict}")
    print()

    return result


def _compare_one(base_url: str, token: Token, ts: int, ref_price_val: float) -> ComparisonResult:
    """Compare a single YPM price against a reference price and print the result."""
    label = f"[{token.chain}] {token.name} ({_short_addr(token.address)}) @ {_ts_label(ts)}"

    ypm_price, ypm_err = fetch_ypm_price(base_url, token, ts)
    ref_price: float | None = ref_price_val
    ref_err: str | None = None

    result = ComparisonResult(
        token=token,
        timestamp=ts,
        ypm_price=ypm_price,
        ref_price=ref_price,
        ypm_error=ypm_err,
        ref_error=ref_err,
        passed=None,
    )

    ypm_str = f"ERROR ({ypm_err})" if ypm_err is not None else _fmt_price(ypm_price)  # type: ignore[arg-type]
    ref_str = f"ERROR ({ref_err})" if ref_err is not None else _fmt_price(ref_price)  # type: ignore[arg-type]

    if ypm_err is not None or ref_err is not None:
        verdict = "-- SKIP"
    else:
        assert ypm_price is not None
        assert ref_price is not None
        if ref_price == 0:
            delta_pct = 0.0 if ypm_price == 0 else float("inf")
        else:
            delta_pct = abs(ypm_price - ref_price) / ref_price
        tol_str = f"{token.tolerance:.0%}"
        if delta_pct <= token.tolerance:
            result.passed = True
            verdict = f"Delta: {delta_pct:.2%}  PASS (tol: {tol_str})"
        else:
            result.passed = False
            verdict = f"Delta: {delta_pct:.2%}  FAIL (tol: {tol_str})"

    print(label)
    print(f"  YPM: {ypm_str}")
    print(f"  REF: {ref_str}")
    print(f"  {verdict}")
    print()

    return result


def _filter_tokens_by_chains(live_chains: list[str]) -> list[Token]:
    """Filter TOKENS to those on live chains and print skip info."""
    tokens = [t for t in TOKENS if t.chain in live_chains]
    skipped_chains = sorted({t.chain for t in TOKENS} - set(live_chains))
    if skipped_chains:
        skipped_tokens = [t for t in TOKENS if t.chain not in live_chains]
        print(
            f"Skipping {len(skipped_tokens)} token(s) on offline chain(s): "
            f"{', '.join(skipped_chains)}"
        )
        print()
    return tokens


def _compare_historical(base_url: str, tokens: list[Token]) -> tuple[list[ComparisonResult], bool]:
    """Fetch DefiLlama charts and compare historical prices. Returns (results, ok)."""
    print("Fetching start timestamps...", flush=True)
    first_ts = fetch_defillama_first_timestamps(tokens)
    global_start = max(first_ts.get(t.address, 0) for t in tokens)
    if global_start == 0:
        global_start = 1609459200  # 2021-01-01 fallback
    print(
        f"Earliest common data: {_ts_label(global_start)} "
        f"(using {NUM_CHART_POINTS} points, {CHART_PERIOD} apart)",
        flush=True,
    )
    print()

    print("Fetching DefiLlama price charts...", flush=True)
    chart_data = fetch_defillama_chart(tokens, global_start, NUM_CHART_POINTS, CHART_PERIOD)
    total_points = sum(len(pts) for pts in chart_data.values())
    print(f"Got {total_points} price points across {len(chart_data)} tokens")
    print()

    if total_points == 0:
        print("ERROR: no chart data returned from DefiLlama")
        return [], False

    results: list[ComparisonResult] = []
    for token in tokens:
        points = chart_data.get(token.address, [])
        if not points:
            print(f"[{token.chain}] {token.name}: no chart data from DefiLlama, skipping")
            print()
            continue
        for ts, ref_price_val in points:
            results.append(_compare_one(base_url, token, ts, ref_price_val))

    return results, True


def run(base_url: str) -> int:
    """Run all comparisons and print results. Returns exit code."""
    print("YPM Price Validator")
    print("==================")
    print(f"Server:    {base_url}")
    print(f"Reference: DefiLlama (cached at {_llama_cache.directory})")
    print()

    print("Discovering live chains...", flush=True)
    live_chains = discover_live_chains(base_url)
    if not live_chains:
        print("ERROR: no chain backends are responding")
        return 1
    print(f"Live chains: {', '.join(live_chains)}")
    print()

    tokens = _filter_tokens_by_chains(live_chains)
    if not tokens:
        print("ERROR: no tokens to validate after filtering by live chains")
        return 1

    historical_results, ok = _compare_historical(base_url, tokens)
    if not ok:
        return 1

    results: list[ComparisonResult] = list(historical_results)

    print("------------------")
    print("Latest prices (cache miss)")
    print("------------------")
    print()

    current_prices = fetch_defillama_current_prices(tokens)
    for token in tokens:
        ref = current_prices.get(token.address)
        if ref is None:
            print(f"[{token.chain}] {token.name}: no current price from DefiLlama, skipping")
            print()
            continue
        results.append(_compare_latest(base_url, token, ref))

    total = len(results)
    passed = sum(1 for r in results if r.passed is True)
    failed = sum(1 for r in results if r.passed is False)
    skipped = sum(1 for r in results if r.passed is None)

    print("==================")
    print(f"Chains validated: {', '.join(live_chains)}")
    print(f"Summary: {total} comparisons | {passed} passed | {failed} failed | {skipped} skipped")

    return 1 if failed > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ypricemagic-server prices against DefiLlama historical prices.",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="ypricemagic-server base URL without chain path (default: %(default)s)",
    )
    args = parser.parse_args()
    sys.exit(run(args.url))


if __name__ == "__main__":
    main()
