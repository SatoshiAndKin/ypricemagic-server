#!/usr/bin/env python3
"""Smoke-test Ethereum and Base prices through the browser UI.

Requires:
    - docker compose stack running (``docker compose up``)
    - playwright browsers installed (``playwright install chromium``)

Usage:
    python scripts/test_web_ui.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page, Response, expect, sync_playwright

TOKENS: list[tuple[str, str]] = [
    ("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
    ("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7"),
    ("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
]

CHAIN_TOKENS = {
    "ethereum": TOKENS,
    "base": [
        ("USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"),
        ("WETH", "0x4200000000000000000000000000000000000006"),
    ],
}

# Allow the server's 300-second timeout response to reach the browser.
PRICE_TIMEOUT_MS = 315_000


def fetch_price_via_ui(
    page: Page, token_name: str, token_address: str, chain: str = "ethereum"
) -> dict[str, Any]:
    """Assert the requested chain/token response and its displayed price agree."""
    started = time.monotonic()
    print(f"  [{chain}/{token_name}] entering address {token_address}")
    page.get_by_label("Chain", exact=True).select_option(chain)
    token_input = page.get_by_placeholder("0x... or symbol")
    clear_btn = page.get_by_role("button", name="Clear token")
    if clear_btn.is_visible():
        clear_btn.click()
    token_input.fill(token_address)
    page.keyboard.press("Escape")

    def matches(response: Response) -> bool:
        url = urlsplit(response.url)
        return (
            url.path == f"/{chain}/price"
            and parse_qs(url.query).get("token", [""])[0].lower() == token_address.lower()
            and response.status not in (301, 302, 303, 307, 308)
        )

    with page.expect_response(matches, timeout=PRICE_TIMEOUT_MS) as pending:
        page.get_by_role("button", name="Get Price").click()
    response = pending.value
    assert response.status == 200, f"HTTP {response.status}: {response.text()}"
    data: dict[str, Any] = response.json()
    assert data["chain"] == chain, data
    assert data["token"].lower() == token_address.lower(), data
    price = data["price"]
    assert type(price) in (float, int) and math.isfinite(price) and price > 0, data
    result_card = page.locator(".result-card")
    expect(result_card).to_be_visible(timeout=PRICE_TIMEOUT_MS)
    value = result_card.locator(".result-value-number").first
    expected = page.evaluate("price => '$' + price.toFixed(4)", price)
    expect(value).to_have_text(expected, timeout=5000)
    price_text = value.inner_text()
    print(f"  [{chain}/{token_name}] price = {price_text} OK")
    return {
        "chain": chain,
        "token_name": token_name,
        "token": token_address,
        "status": response.status,
        "api_price": price,
        "rendered_price": price_text,
        "seconds": time.monotonic() - started,
        "final_url": page.url,
        "passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    parser.add_argument(
        "--chains", nargs="+", choices=tuple(CHAIN_TOKENS), default=list(CHAIN_TOKENS)
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    failures: list[str] = []
    results: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page()

        print(f"Navigating to {args.base_url} ...")
        page.goto(args.base_url, wait_until="networkidle")

        for chain in args.chains:
            for token_name, token_address in CHAIN_TOKENS[chain]:
                try:
                    results.append(fetch_price_via_ui(page, token_name, token_address, chain))
                except Exception as error:
                    print(f"  [{chain}/{token_name}] FAILED: {error}")
                    failures.append(f"{chain}/{token_name}")
                    results.append(
                        {
                            "chain": chain,
                            "token": token_address,
                            "passed": False,
                            "error": str(error),
                        }
                    )
                if args.report:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    args.report.write_text(
                        json.dumps({"passed": not failures, "results": results}, indent=2) + "\n"
                    )

        browser.close()

    if failures:
        print(f"\nFAILED: {', '.join(failures)}")
        return 1

    print("\nAll tokens passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
