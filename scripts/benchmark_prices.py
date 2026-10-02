#!/usr/bin/env python3
"""Measure first, repeated, changed-amount and distinct-block pricing requests."""

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CHAINS = {
    "ethereum": (
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        19000000,
        0.9989039883929369,
    ),
    "base": (
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "0x4200000000000000000000000000000000000006",
        24000000,
        0.990993596876513,
    ),
}


class Benchmark:
    def __init__(self, url: str, report: Path) -> None:
        self.url = url.rstrip("/")
        self.report = report
        self.rows: list[dict[str, Any]] = []

    def request(
        self, phase: str, chain: str, endpoint: str, params: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self.url}/{chain}/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        started = time.monotonic()
        row: dict[str, Any] = {"phase": phase, "chain": chain, "params": params}
        try:
            with urllib.request.urlopen(url, timeout=315) as response:
                body = json.load(response)
                row.update(status=response.status, body=body, final_url=response.url)
                entries = body if isinstance(body, list) else [body]
                if endpoint in ("price", "prices"):
                    assert all(
                        isinstance(item.get("price"), (int, float))
                        and math.isfinite(item["price"])
                        and item["price"] > 0
                        for item in entries
                    ), body
                row["passed"] = True
                return body
        except urllib.error.HTTPError as error:
            row.update(status=error.code, passed=False, error=error.read().decode(errors="replace"))
            raise
        except Exception as error:
            row.update(passed=False, error=f"{type(error).__name__}: {error}")
            raise
        finally:
            row["seconds"] = time.monotonic() - started
            self.rows.append(row)
            self.report.parent.mkdir(parents=True, exist_ok=True)
            self.report.write_text(json.dumps(self.rows, indent=2))
            print(
                f"{chain} {phase}: {row['seconds']:.3f}s {'PASS' if row.get('passed') else 'FAIL'}",
                flush=True,
            )

    def chain(self, chain: str) -> None:
        token, unseen, historical, expected = CHAINS[chain]
        params: dict[str, Any] = {"token": token, "block": historical, "amount": "1000.000001"}
        first = self.request("historical-first", chain, "price", params)
        assert math.isclose(first["price"], expected, rel_tol=1e-9), first
        repeat = self.request("historical-repeat", chain, "price", params)
        assert repeat["price"] == first["price"] and repeat["cached"] is False
        self.request("changed-amount", chain, "price", {**params, "amount": "1001.000001"})
        mixed = self.request(
            "mixed-order",
            chain,
            "prices",
            {
                "tokens": f"{token},{token},{token}",
                "block": historical,
                "amounts": "1000.000001,,1001.000001",
            },
        )
        assert [item["token"].lower() for item in mixed] == [token.lower()] * 3
        assert math.isclose(mixed[0]["price"], first["price"], rel_tol=1e-9)
        self.request(
            "unseen-token-first",
            chain,
            "price",
            {"token": unseen, "block": historical, "amount": "0.1"},
        )
        head = self.request("current-health", chain, "health")["block"]
        for offset in range(2, 5):
            current = {"token": token, "block": head - offset, "amount": "1000.000001"}
            result = self.request(f"distinct-block-{offset}", chain, "price", current)
            same = self.request(f"distinct-block-{offset}-repeat", chain, "price", current)
            assert result["price"] == same["price"] and same["cached"] is False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://ypricemagic.stytt.com")
    parser.add_argument("--report", type=Path, default=Path("benchmark-prices.json"))
    parser.add_argument("--chains", nargs="+", choices=CHAINS, default=list(CHAINS))
    args = parser.parse_args()
    benchmark = Benchmark(args.url, args.report)
    failed = False
    for chain in args.chains:
        try:
            benchmark.chain(chain)
        except Exception as error:
            print(f"{chain} acceptance failed: {type(error).__name__}: {error}", flush=True)
            failed = True
            benchmark.rows.append(
                {
                    "chain": chain,
                    "phase": "acceptance",
                    "passed": False,
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            args.report.write_text(json.dumps(benchmark.rows, indent=2))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
