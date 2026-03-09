"""Fetch the Uniswap default token list and filter to supported chains."""

import json
import sys
import urllib.request
from pathlib import Path

UNISWAP_URL = "https://tokens.uniswap.org"
SUPPORTED_CHAIN_IDS = {1, 10, 42161, 8453}

ROOT = Path(__file__).parent.parent
TARGETS = [
    ROOT / "frontend" / "public" / "tokenlists" / "uniswap-default.json",
]


def main() -> None:
    sys.stdout.write(f"Fetching {UNISWAP_URL}...\n")
    req = urllib.request.Request(UNISWAP_URL, headers={"User-Agent": "ypricemagic-server/1.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    original_count = len(data["tokens"])
    data["tokens"] = [t for t in data["tokens"] if t["chainId"] in SUPPORTED_CHAIN_IDS]
    filtered_count = len(data["tokens"])

    sys.stdout.write(f"Filtered {original_count} -> {filtered_count} tokens ")
    sys.stdout.write(f"(chains: {sorted(SUPPORTED_CHAIN_IDS)})\n")

    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2) + "\n")
        sys.stdout.write(f"Written to {target}\n")


if __name__ == "__main__":
    main()
