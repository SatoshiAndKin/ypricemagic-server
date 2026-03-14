#!/usr/bin/env python3
"""Smoke-test: fetch USDC, USDT, WETH prices through the browser UI.

Requires:
    - docker compose stack running (``docker compose up``)
    - playwright browsers installed (``playwright install chromium``)

Usage:
    python scripts/test_web_ui.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import re
import sys

from playwright.sync_api import Page, expect, sync_playwright

TOKENS: list[tuple[str, str]] = [
    ("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
    ("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7"),
    ("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
]

# ypricemagic can be slow on first lookup; 5 minutes per token.
PRICE_TIMEOUT_MS = 300_000


def fetch_price_via_ui(page: Page, token_name: str, token_address: str) -> None:
    """Type a token address, submit, and assert a price result appears."""
    print(f"  [{token_name}] entering address {token_address[:10]}...")

    token_input = page.get_by_placeholder("0x... or symbol")
    clear_btn = page.get_by_role("button", name="Clear token")

    # Clear any previous value
    if clear_btn.is_visible():
        clear_btn.click()

    token_input.fill(token_address)
    # Close autocomplete dropdown if it opened
    page.keyboard.press("Escape")

    page.get_by_role("button", name="Get Price").click()

    print(f"  [{token_name}] waiting for result (up to {PRICE_TIMEOUT_MS // 1000}s)...")

    result_card = page.locator(".result-card")
    expect(result_card).to_be_visible(timeout=PRICE_TIMEOUT_MS)

    price_text = result_card.locator(".result-value-number").first.inner_text(timeout=5000)
    print(f"  [{token_name}] price = {price_text}")

    # Price should look like "$<number>"
    assert re.match(r"\$\d+(\.\d+)?", price_text), (
        f"[{token_name}] unexpected price format: {price_text!r}"
    )

    # Price should not be $0.0000
    numeric = float(price_text.lstrip("$"))
    assert numeric > 0, f"[{token_name}] price is zero"

    print(f"  [{token_name}] OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    args = parser.parse_args()

    failures: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page()

        print(f"Navigating to {args.base_url} ...")
        page.goto(args.base_url, wait_until="networkidle")

        for token_name, token_address in TOKENS:
            try:
                fetch_price_via_ui(page, token_name, token_address)
            except Exception as e:
                print(f"  [{token_name}] FAILED: {e}")
                failures.append(token_name)

        browser.close()

    if failures:
        print(f"\nFAILED: {', '.join(failures)}")
        return 1

    print("\nAll tokens passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
