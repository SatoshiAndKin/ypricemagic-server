#!/usr/bin/env python3
"""Compare ypricemagic-server prices against DefiLlama historical prices."""

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


@dataclass(frozen=True)
class Token:
    name: str
    address: str
    tolerance: float


TOKENS: list[Token] = [
    Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", STABLECOIN_TOLERANCE),
    Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", STABLECOIN_TOLERANCE),
    Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", STABLECOIN_TOLERANCE),
    Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", VOLATILE_TOLERANCE),
    Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", VOLATILE_TOLERANCE),
    Token("UNI", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", VOLATILE_TOLERANCE),
    Token("LINK", "0x514910771AF9Ca656af840dff83E8264EcF986CA", VOLATILE_TOLERANCE),
    Token("AAVE", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9", VOLATILE_TOLERANCE),
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


def _http_get_json(url: str) -> object:
    """Perform a GET request and return parsed JSON."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        body = resp.read().decode()
    return json.loads(body)


# ---------------------------------------------------------------------------
# API callers
# ---------------------------------------------------------------------------


def fetch_ypm_price(
    base_url: str, token: Token, timestamp: int | None = None
) -> tuple[float | None, str | None]:
    """Fetch a price from ypricemagic-server. Returns (price, error).

    If *timestamp* is None, fetches the latest price (no timestamp param).
    """
    if timestamp is not None:
        url = f"{base_url}/price?token={token.address}&timestamp={timestamp}"
    else:
        url = f"{base_url}/price?token={token.address}"
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
        cache_key = f"first:{token.address}"
        cached = _llama_cache.get(cache_key)
        if cached is not None:
            results[token.address] = cached
        else:
            uncached.append(token)

    if not uncached:
        return results

    coins = ",".join(f"ethereum:{t.address}" for t in uncached)
    url = f"https://coins.llama.fi/prices/first/{coins}"
    try:
        data = _http_get_json(url)
        if isinstance(data, dict):
            for token in uncached:
                key = f"ethereum:{token.address}"
                entry = data.get("coins", {}).get(key, {})
                ts = entry.get("timestamp")
                if isinstance(ts, int | float):
                    results[token.address] = int(ts)
                    _llama_cache.set(f"first:{token.address}", int(ts))
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
    coins = ",".join(f"ethereum:{t.address}" for t in tokens)
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
        key = f"ethereum:{token.address}"
        entry = data.get("coins", {}).get(key, {})
        prices = entry.get("prices", [])
        points: list[tuple[int, float]] = []
        for p in prices:
            ts = p.get("timestamp")
            price = p.get("price")
            if ts is not None and price is not None:
                _llama_cache.set(f"{token.address}:{ts}", float(price))
                points.append((int(ts), float(price)))
        results[token.address] = points

    return results


def get_defillama_price(
    token: Token,
    timestamp: int,
) -> tuple[float | None, str | None]:
    """Get a single cached DefiLlama price. Returns (price, error)."""
    cache_key = f"{token.address}:{timestamp}"
    cached = _llama_cache.get(cache_key)
    if cached is not None:
        return (float(cached), None)
    return (None, "not in cache")


def fetch_defillama_current_prices(tokens: list[Token]) -> dict[str, float]:
    """Fetch current prices from DefiLlama /prices/current/. Returns {address: price}."""
    coins = ",".join(f"ethereum:{t.address}" for t in tokens)
    url = f"https://coins.llama.fi/prices/current/{coins}"
    try:
        data = _http_get_json(url)
        if not isinstance(data, dict):
            return {}
        results: dict[str, float] = {}
        for token in tokens:
            key = f"ethereum:{token.address}"
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
    label = f"{token.name} ({_short_addr(token.address)}) @ latest"

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
    label = f"{token.name} ({_short_addr(token.address)}) @ {_ts_label(ts)}"

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


def run(base_url: str) -> int:
    """Run all comparisons and print results. Returns exit code."""
    print("YPM Price Validator")
    print("==================")
    print(f"Server:    {base_url}")
    print(f"Reference: DefiLlama (cached at {_llama_cache.directory})")
    print()

    # 1. Find earliest available timestamps per token
    print("Fetching start timestamps...", flush=True)
    first_ts = fetch_defillama_first_timestamps(TOKENS)
    global_start = max(first_ts.get(t.address, 0) for t in TOKENS)
    if global_start == 0:
        global_start = 1609459200  # 2021-01-01 fallback
    print(
        f"Earliest common data: {_ts_label(global_start)} "
        f"(using {NUM_CHART_POINTS} points, {CHART_PERIOD} apart)",
        flush=True,
    )
    print()

    # 2. Fetch reference price charts per token (each gets its own timestamps)
    print("Fetching DefiLlama price charts...", flush=True)
    chart_data = fetch_defillama_chart(TOKENS, global_start, NUM_CHART_POINTS, CHART_PERIOD)

    total_points = sum(len(pts) for pts in chart_data.values())
    print(f"Got {total_points} price points across {len(chart_data)} tokens")
    print()

    if total_points == 0:
        print("ERROR: no chart data returned from DefiLlama")
        return 1

    # 3. Compare each token at its own chart timestamps
    results: list[ComparisonResult] = []

    for token in TOKENS:
        points = chart_data.get(token.address, [])
        if not points:
            print(f"{token.name}: no chart data from DefiLlama, skipping")
            print()
            continue

        for ts, ref_price_val in points:
            result = _compare_one(base_url, token, ts, ref_price_val)
            results.append(result)

    # 4. Compare latest (current block) prices -- always a cache miss
    print("------------------")
    print("Latest prices (cache miss)")
    print("------------------")
    print()

    current_prices = fetch_defillama_current_prices(TOKENS)
    for token in TOKENS:
        ref = current_prices.get(token.address)
        if ref is None:
            print(f"{token.name}: no current price from DefiLlama, skipping")
            print()
            continue
        result = _compare_latest(base_url, token, ref)
        results.append(result)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.passed is True)
    failed = sum(1 for r in results if r.passed is False)
    skipped = sum(1 for r in results if r.passed is None)

    print("==================")
    print(f"Summary: {total} comparisons | {passed} passed | {failed} failed | {skipped} skipped")

    return 1 if failed > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ypricemagic-server prices against DefiLlama historical prices.",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/ethereum",
        help="ypricemagic-server base URL (default: %(default)s)",
    )
    args = parser.parse_args()
    sys.exit(run(args.url))


if __name__ == "__main__":
    main()
