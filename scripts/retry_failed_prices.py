#!/usr/bin/env python3
"""Retry failed price lookups that are stored in the diskcache.

This script scans the cache for *error* entries (failed price lookups that
were cached with a TTL) and re-requests each one through the running
ypricemagic-server API.

On success: the API handler overwrites the error entry with the real price.
On failure: the API handler refreshes the error entry with a new TTL.

This script only processes error entries — it never touches successful price
entries.

Usage
-----
    # Retry against the local Docker stack (default)
    python scripts/retry_failed_prices.py

    # Point at a different server
    python scripts/retry_failed_prices.py --base-url http://localhost:8001

    # Limit concurrency (default: 4 parallel requests)
    python scripts/retry_failed_prices.py --concurrency 8

    # Dry-run: list errors without retrying
    python scripts/retry_failed_prices.py --dry-run

    # Override cache directory
    CACHE_DIR=/path/to/cache python scripts/retry_failed_prices.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cache import get_cached_errors


async def _retry_one(
    client: httpx.AsyncClient,
    base_url: str,
    chain: str,
    token: str,
    block: int,
    dry_run: bool,
) -> tuple[str, int, bool, str]:
    """Retry a single failed price lookup.

    Returns ``(token, block, success, message)``.
    """
    if dry_run:
        return token, block, False, "dry-run, skipped"

    url = f"{base_url}/{chain}/price"
    params = {"token": token, "block": str(block)}
    try:
        resp = await client.get(url, params=params, timeout=300.0)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get("price")
            return token, block, True, f"price={price}"
        else:
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else resp.text
            )
            err = body.get("error", resp.text) if isinstance(body, dict) else resp.text
            return token, block, False, f"HTTP {resp.status_code}: {err}"
    except Exception as exc:
        return token, block, False, f"request_error: {exc}"


async def retry_all(
    base_url: str,
    chain: str,
    concurrency: int,
    dry_run: bool,
) -> None:
    """Scan cache for error entries and retry each one."""
    errors = list(get_cached_errors())
    if not errors:
        print("No error entries found in cache.")
        return

    print(f"Found {len(errors)} error entr{'y' if len(errors) == 1 else 'ies'} to retry.")
    if dry_run:
        for token, block, entry in errors:
            print(
                f"  {token}:{block}  error={entry.get('error')}  cached_at={entry.get('cached_at')}"
            )
        return

    sem = asyncio.Semaphore(concurrency)
    success_count = 0
    failure_count = 0

    async def _bounded_retry(client: httpx.AsyncClient, token: str, block: int) -> None:
        nonlocal success_count, failure_count
        async with sem:
            _, _, ok, msg = await _retry_one(client, base_url, chain, token, block, dry_run)
            status = "✓" if ok else "✗"
            print(f"  {status} {token}:{block}  {msg}")
            if ok:
                success_count += 1
            else:
                failure_count += 1

    async with httpx.AsyncClient() as client:
        tasks = [
            asyncio.create_task(_bounded_retry(client, token, block)) for token, block, _ in errors
        ]
        await asyncio.gather(*tasks)

    print(
        f"\nDone: {success_count} succeeded, {failure_count} failed "
        f"(failed entries refreshed with new TTL)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retry cached error entries in ypricemagic-server.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the ypricemagic-server API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--chain",
        default="ethereum",
        help="Chain name path segment (default: ethereum)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Maximum number of parallel retry requests (default: 4)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List error entries without sending retry requests",
    )
    args = parser.parse_args()

    asyncio.run(
        retry_all(
            base_url=args.base_url,
            chain=args.chain,
            concurrency=args.concurrency,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
