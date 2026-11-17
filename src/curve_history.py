"""Seed pod-local Curve event history through a finalized Ethereum block."""

import asyncio
import json
from pathlib import Path
from typing import Any

from src.logger import get_logger

logger = get_logger("curve_history")
_CHECKPOINT = Path(__file__).with_suffix(".json")


async def seed_curve_history() -> None:
    """Skip historical RPC scans when the immutable checkpoint is canonical."""
    try:
        await _seed()
    except Exception as error:
        # Startup still requires the ordinary RPC scan when the seed is unavailable.
        logger.warning("curve_history_seed_unavailable", error_type=type(error).__name__)


async def _seed() -> None:
    from dank_mids.brownie_patch import dank_eth
    from y import ENVIRONMENT_VARIABLES as ENVS
    from y._db.common import default_filter_threads
    from y._db.utils.logs import LogCache, bulk_insert_factory
    from y.constants import CHAINID

    if CHAINID != 1 or str(ENVS.DB_PROVIDER) != "sqlite":
        return

    checkpoint = json.loads(_CHECKPOINT.read_bytes())
    through = int(checkpoint["through"])
    sources = checkpoint["sources"]
    if checkpoint["chain_id"] != CHAINID or not sources:
        raise ValueError("Invalid Curve checkpoint")

    pending = []
    for source in sources:
        cache = LogCache(source["address"], None)
        first = int(source["from"])
        if await default_filter_threads.run(cache.is_cached_thru, first) < through:
            pending.append((cache, first, source))

    if not pending:
        return

    # A provider that cannot attest the checkpoint follows the normal cold path.
    async with asyncio.timeout(5):
        block = await dank_eth.get_block(through)
    if bytes(block["hash"]) != bytes.fromhex(checkpoint["hash"].removeprefix("0x")):
        logger.warning("curve_history_seed_not_canonical", block=through)
        return

    logs = [
        event for _, first, source in pending for event in _decode_source(source, first, through)
    ]

    # Publish coverage only after all checkpoint events are durable in the local DB.
    await bulk_insert_factory(logs)
    for cache, first, _ in pending:
        await default_filter_threads.run(cache.set_metadata, first, through)

    logger.info("curve_history_seed_loaded", through=through, events=len(logs))


def _decode_source(source: dict[str, Any], first: int, through: int) -> list[Any]:
    from y._db.utils.logs import _decode_log

    logs = []
    for raw in source["logs"]:
        event = _decode_log(json.dumps(raw).encode())
        block_number, address = event.blockNumber, event.address
        if (
            event.removed
            or block_number is None
            or address is None
            or not first <= block_number <= through
            or address.lower() != source["address"].lower()
        ):
            raise ValueError("Curve event is outside its checkpoint source")
        logs.append(event)
    return logs
