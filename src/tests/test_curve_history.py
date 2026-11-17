import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src import curve_history

_ADDRESS = "0x0000000022D53366457F9d5E68Ec105046FC4383"
_ANCHOR = bytes.fromhex("a7cc3d2df6678209464666c274d24afb7c45496b458934bdc783b3a218bc76da")


@pytest.fixture
def seed_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    checkpoint = tmp_path / "curve.json"
    checkpoint.write_text(
        json.dumps(
            {
                "chain_id": 1,
                "through": 200,
                "hash": "0x" + _ANCHOR.hex(),
                "sources": [{"address": _ADDRESS, "from": 100, "logs": [[]]}],
            }
        )
    )
    monkeypatch.setattr(curve_history, "_CHECKPOINT", checkpoint)
    calls = Mock()
    cache = calls.cache
    cache.is_cached_thru.return_value = 0
    event = SimpleNamespace(removed=False, blockNumber=150, address=_ADDRESS)

    async def run(func, *args):  # type: ignore[no-untyped-def]
        return func(*args)

    common = SimpleNamespace(default_filter_threads=SimpleNamespace(run=run))
    logs = SimpleNamespace(LogCache=Mock(return_value=cache), _decode_log=Mock(return_value=event))
    logs.bulk_insert_factory = AsyncMock()
    calls.attach_mock(logs.bulk_insert_factory, "insert")
    dank_eth = SimpleNamespace(get_block=AsyncMock(return_value={"hash": _ANCHOR}))
    monkeypatch.setitem(sys.modules, "dank_mids.brownie_patch", SimpleNamespace(dank_eth=dank_eth))
    monkeypatch.setitem(sys.modules, "y._db.common", common)
    monkeypatch.setitem(sys.modules, "y._db.utils.logs", logs)
    monkeypatch.setattr(sys.modules["y.constants"], "CHAINID", 1)
    monkeypatch.setattr(
        sys.modules["y"], "ENVIRONMENT_VARIABLES", SimpleNamespace(DB_PROVIDER="sqlite")
    )
    return SimpleNamespace(cache=cache, calls=calls, event=event, dank_eth=dank_eth, logs=logs)


@pytest.mark.asyncio
async def test_seed_validates_anchor_and_inserts_before_coverage(
    seed_runtime: SimpleNamespace,
) -> None:
    await curve_history.seed_curve_history()
    seed_runtime.dank_eth.get_block.assert_awaited_once_with(200)
    seed_runtime.logs.bulk_insert_factory.assert_awaited_once_with([seed_runtime.event])
    seed_runtime.cache.set_metadata.assert_called_once_with(100, 200)
    assert [item[0] for item in seed_runtime.calls.mock_calls] == [
        "cache.is_cached_thru",
        "insert",
        "cache.set_metadata",
    ]


@pytest.mark.asyncio
async def test_seed_skips_local_coverage(seed_runtime: SimpleNamespace) -> None:
    seed_runtime.cache.is_cached_thru.return_value = 201
    await curve_history.seed_curve_history()
    seed_runtime.dank_eth.get_block.assert_not_awaited()
    seed_runtime.logs.bulk_insert_factory.assert_not_awaited()
    seed_runtime.cache.set_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_seed_rejects_other_history(seed_runtime: SimpleNamespace) -> None:
    seed_runtime.dank_eth.get_block.return_value = {"hash": b"\x00" * 32}
    await curve_history.seed_curve_history()
    seed_runtime.logs.bulk_insert_factory.assert_not_awaited()
    seed_runtime.cache.set_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_seed_rejects_invalid_logs(seed_runtime: SimpleNamespace) -> None:
    seed_runtime.event.blockNumber = 201
    await curve_history.seed_curve_history()
    seed_runtime.logs.bulk_insert_factory.assert_not_awaited()
    seed_runtime.cache.set_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_seed_write_failure_does_not_publish_coverage(seed_runtime: SimpleNamespace) -> None:
    seed_runtime.logs.bulk_insert_factory.side_effect = OSError()
    await curve_history.seed_curve_history()
    seed_runtime.cache.set_metadata.assert_not_called()
