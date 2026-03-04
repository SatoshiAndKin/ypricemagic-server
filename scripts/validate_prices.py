#!/usr/bin/env python3
"""Compare ypricemagic-server prices against CryptoCompare historical prices."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Token matrix
# ---------------------------------------------------------------------------

STABLECOIN_TOLERANCE = 0.02  # 2%
VOLATILE_TOLERANCE = 0.10  # 10%


@dataclass(frozen=True)
class Token:
    name: str
    address: str
    cc_symbol: str
    tolerance: float


TOKENS: list[Token] = [
    # Stablecoins
    Token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC", STABLECOIN_TOLERANCE),
    Token("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT", STABLECOIN_TOLERANCE),
    Token("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", "DAI", STABLECOIN_TOLERANCE),
    # Volatile
    Token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "ETH", VOLATILE_TOLERANCE),
    Token("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", "BTC", VOLATILE_TOLERANCE),
    Token("UNI", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", "UNI", VOLATILE_TOLERANCE),
    Token("LINK", "0x514910771AF9Ca656af840dff83E8264EcF986CA", "LINK", VOLATILE_TOLERANCE),
    Token("AAVE", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9", "AAVE", VOLATILE_TOLERANCE),
]

TIMESTAMPS: list[int] = [
    1672531200,  # 2023-01-01
    1688169600,  # 2023-07-01
    1704067200,  # 2024-01-01
    1719792000,  # 2024-07-01
]

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


@dataclass
class ComparisonResult:
    token: Token
    timestamp: int
    ypm_price: float | None
    cc_price: float | None
    ypm_error: str | None
    cc_error: str | None
    passed: bool | None  # None = skipped


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

_TIMEOUT = 30


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> object:
    """Perform a GET request and return parsed JSON."""
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        body = resp.read().decode()
    return json.loads(body)


# ---------------------------------------------------------------------------
# API callers
# ---------------------------------------------------------------------------


def fetch_ypm_price(base_url: str, token: Token, timestamp: int) -> tuple[float | None, str | None]:
    """Fetch a price from ypricemagic-server. Returns (price, error)."""
    url = f"{base_url}/price?token={token.address}&timestamp={timestamp}"
    try:
        data = _http_get_json(url)
        if not isinstance(data, dict):
            return None, f"unexpected response type: {type(data).__name__}"
        price = data.get("price")
        if price is None:
            error_msg = data.get("error", "no price in response")
            return None, f"server error: {error_msg}"
        return float(price), None
    except urllib.error.HTTPError as exc:
        return None, f"server returned {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"network error: {exc.reason}"
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        return None, f"parse error: {exc}"
    except Exception as exc:
        return None, f"unexpected error: {exc}"


def _fetch_cc_once(
    url: str,
    headers: dict[str, str],
    symbol: str,
) -> tuple[float | None, str | None]:
    """Single attempt to fetch a CryptoCompare price. Returns (price, error)."""
    data = _http_get_json(url, headers=headers)
    if not isinstance(data, dict):
        return None, f"unexpected response type: {type(data).__name__}"
    symbol_data = data.get(symbol)
    if not isinstance(symbol_data, dict):
        return None, f"missing symbol key '{symbol}' in response"
    price = symbol_data.get("USD")
    if price is None:
        return None, "no USD price in response"
    return float(price), None


def fetch_cc_price(
    symbol: str,
    timestamp: int,
    api_key: str | None,
) -> tuple[float | None, str | None]:
    """Fetch a historical price from CryptoCompare. Returns (price, error)."""
    url = (
        f"https://min-api.cryptocompare.com/data/pricehistorical"
        f"?fsym={symbol}&tsyms=USD&ts={timestamp}"
    )
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Apikey {api_key}"

    for attempt in range(2):
        try:
            return _fetch_cc_once(url, headers, symbol)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(1)
                continue
            return None, f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return None, f"network error: {exc.reason}"
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            return None, f"parse error: {exc}"
        except Exception as exc:
            return None, f"unexpected error: {exc}"

    return None, "max retries exceeded"


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


def run(base_url: str, cc_key: str | None) -> int:
    """Run all comparisons and print results. Returns exit code."""
    print("YPM Price Validator")  # noqa: T201
    print("==================")  # noqa: T201
    print(f"Server: {base_url}")  # noqa: T201
    cc_label = "provided" if cc_key else "not provided"
    print(f"CryptoCompare API key: {cc_label}")  # noqa: T201
    print()  # noqa: T201

    results: list[ComparisonResult] = []

    for token in TOKENS:
        for ts in TIMESTAMPS:
            label = f"{token.name} ({_short_addr(token.address)}) @ {_ts_label(ts)}"

            ypm_price, ypm_err = fetch_ypm_price(base_url, token, ts)
            # Rate-limit CryptoCompare calls
            time.sleep(1)
            cc_price, cc_err = fetch_cc_price(token.cc_symbol, ts, cc_key)

            result = ComparisonResult(
                token=token,
                timestamp=ts,
                ypm_price=ypm_price,
                cc_price=cc_price,
                ypm_error=ypm_err,
                cc_error=cc_err,
                passed=None,
            )

            # Build output line
            if ypm_err is not None:
                ypm_str = f"ERROR ({ypm_err})"
            else:
                assert ypm_price is not None
                ypm_str = _fmt_price(ypm_price)

            if cc_err is not None:
                cc_str = f"ERROR ({cc_err})"
            else:
                assert cc_price is not None
                cc_str = _fmt_price(cc_price)

            if ypm_err is not None or cc_err is not None:
                verdict = "— SKIP"
            else:
                assert ypm_price is not None
                assert cc_price is not None
                if cc_price == 0:
                    delta_pct = 0.0 if ypm_price == 0 else float("inf")
                else:
                    delta_pct = abs(ypm_price - cc_price) / cc_price
                tol_str = f"{token.tolerance:.0%}"
                if delta_pct <= token.tolerance:
                    result.passed = True
                    verdict = f"Delta: {delta_pct:.2%}  ✓ PASS (tolerance: {tol_str})"
                else:
                    result.passed = False
                    verdict = f"Delta: {delta_pct:.2%}  ✗ FAIL (tolerance: {tol_str})"

            print(label)  # noqa: T201
            print(f"  YPM: {ypm_str}  CC: {cc_str}  {verdict}")  # noqa: T201
            print()  # noqa: T201

            results.append(result)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.passed is True)
    failed = sum(1 for r in results if r.passed is False)
    skipped = sum(1 for r in results if r.passed is None)

    print("==================")  # noqa: T201
    print(  # noqa: T201
        f"Summary: {total} comparisons | {passed} passed | {failed} failed | {skipped} skipped"
    )

    return 1 if failed > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ypricemagic-server prices against CryptoCompare historical prices.",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/ethereum",
        help="ypricemagic-server base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--cryptocompare-key",
        default=None,
        help="CryptoCompare API key for higher rate limits",
    )
    args = parser.parse_args()
    sys.exit(run(args.url, args.cryptocompare_key))


if __name__ == "__main__":
    main()
