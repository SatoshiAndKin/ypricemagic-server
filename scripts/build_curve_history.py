#!/usr/bin/env python3
"""Regenerate the optional Curve registry history checkpoint from Ethereum RPC."""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

# The registry scan starts at the oldest deployment for both registries.
SOURCES = {
    "0x0000000022D53366457F9d5E68Ec105046FC4383": 11_153_725,
    "0x90E00ACe148ca3b23Ac1bC8C240C2a7Dd9c2d7f5": 12_195_750,
    "0x8F942C20D02bEfc377D41445793068908E2250D0": 12_195_750,
}
OUTPUT = Path(__file__).resolve().parents[1] / "src" / "curve_history.json"


def rpc(endpoint: str, method: str, params: list[Any]) -> Any:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    request = Request(endpoint, data=body.encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "error" in payload:
        raise ValueError(payload["error"])
    return payload["result"]


def fetch_logs(endpoint: str, first: int, last: int) -> list[dict[str, Any]]:
    try:
        return rpc(
            endpoint,
            "eth_getLogs",
            [{"address": list(SOURCES), "fromBlock": hex(first), "toBlock": hex(last)}],
        )
    except (OSError, ValueError):
        if last - first < 10_000:
            raise
        middle = (first + last) // 2
        return fetch_logs(endpoint, first, middle) + fetch_logs(endpoint, middle + 1, last)


def encode_log(address: str, log: dict[str, Any]) -> list[Any]:
    # Match ypricemagic's pinned array-like Log encoding.
    return [
        [topic[2:].lstrip("0") or "0" for topic in log["topics"]],
        address[2:],
        log["data"][2:],
        log["removed"],
        int(log["blockNumber"], 16),
        log["transactionHash"][2:].lstrip("0") or "0",
        int(log["logIndex"], 16),
        int(log["transactionIndex"], 16),
    ]


def collect_checkpoint(endpoint: str, through: int) -> tuple[str, dict[str, list[list[Any]]]]:
    if int(rpc(endpoint, "eth_chainId", []), 16) != 1:
        raise ValueError("The checkpoint requires Ethereum mainnet")
    finalized = rpc(endpoint, "eth_getBlockByNumber", ["finalized", False])
    if not max(SOURCES.values()) <= through <= int(finalized["number"], 16):
        raise ValueError("Choose a finalized block covering all checkpoint sources")
    block_hash = rpc(endpoint, "eth_getBlockByNumber", [hex(through), False])["hash"]

    span = 200_000
    addresses = {address.lower(): address for address in SOURCES}
    events: dict[str, list[list[Any]]] = {address: [] for address in SOURCES}
    with ThreadPoolExecutor(max_workers=4) as workers:
        ranges = range(min(SOURCES.values()), through + 1, span)
        for logs in workers.map(
            lambda first: fetch_logs(endpoint, first, min(first + span - 1, through)), ranges
        ):
            for log in logs:
                address = addresses[log["address"].lower()]
                row = encode_log(address, log)
                if row[3] or not SOURCES[address] <= row[4] <= through:
                    raise ValueError("Curve event is outside its checkpoint source")
                events[address].append(row)

    if rpc(endpoint, "eth_getBlockByNumber", [hex(through), False])["hash"] != block_hash:
        raise ValueError("Checkpoint block changed during collection")
    for rows in events.values():
        rows.sort(key=lambda row: (row[4], row[6], row[5]))
    return block_hash, events


def render_checkpoint(through: int, block_hash: str, events: dict[str, list[list[Any]]]) -> str:
    sources = []
    for address, first in SOURCES.items():
        rows = ",\n".join(
            "        " + json.dumps(row, separators=(",", ":")) for row in events[address]
        )
        sources.append(
            f'    {{\n      "address": "{address}",\n      "from": {first},'
            f'\n      "logs": [\n{rows}\n      ]\n    }}'
        )
    body = ",\n".join(sources)
    return (
        f'{{\n  "chain_id": 1,\n  "through": {through},\n'
        f'  "hash": "{block_hash}",\n  "sources": [\n{body}\n  ]\n}}\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("block", type=int, help="Ethereum finalized checkpoint block")
    args = parser.parse_args()
    endpoint = os.environ.get("RPC_URL")
    if not endpoint:
        parser.error("Set RPC_URL to an Ethereum mainnet RPC with historical logs")
    try:
        block_hash, events = collect_checkpoint(endpoint, args.block)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Cannot build Curve checkpoint ({type(error).__name__})\n")
    OUTPUT.write_text(render_checkpoint(args.block, block_hash, events))
    print(f"Wrote {sum(map(len, events.values()))} Curve events through block {args.block}")


if __name__ == "__main__":
    main()
