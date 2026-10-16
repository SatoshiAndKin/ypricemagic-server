"""Readiness must fail closed and stay current through asynchronous RPC checks."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from src import server


class NodeNotSynced(Exception):  # noqa: N818
    pass


@pytest.mark.parametrize(
    "error,synced",
    [(NodeNotSynced("behind"), False), (RuntimeError("RPC error"), None), (TimeoutError(), None)],
)
async def test_failed_sync_check_never_reports_healthy(
    monkeypatch: pytest.MonkeyPatch, error: Exception, synced: bool | None
) -> None:
    monkeypatch.setattr("y.time.check_node_async", AsyncMock(side_effect=error))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "chain": "ethereum",
        "block": 19000000,
        "synced": synced,
    }


@pytest.mark.parametrize("phase", ["height", "sync"])
@pytest.mark.parametrize("transition", ["drain", "shutdown", "unready"])
async def test_health_cannot_pass_after_readiness_changes_during_rpc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, phase: str, transition: str
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    drain = tmp_path / "drain"
    original_exists = Path.exists

    def exists(path: Path) -> bool:
        return drain.is_file() if path == Path("/tmp/drain") else original_exists(path)

    monkeypatch.setattr(Path, "exists", exists)

    async def height() -> int:
        if phase == "height":
            entered.set()
            await release.wait()
        return 19000000

    async def synced() -> None:
        if phase == "sync":
            entered.set()
            await release.wait()

    monkeypatch.setattr(server, "_head_block", height)
    monkeypatch.setattr("y.time.check_node_async", synced)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        task = asyncio.create_task(client.get("/health"))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            if transition == "drain":
                drain.touch()
            elif transition == "shutdown":
                server._shutdown_event.set()
            else:
                server.app.state.ready = False
        finally:
            release.set()
            response = await task
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


async def test_health_waits_for_required_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initializing, initialized, ready, stop = (asyncio.Event() for _ in range(4))

    async def initialize(registry: Any) -> None:
        initializing.set()
        await initialized.wait()

    async def serve() -> None:
        async with server.lifespan(server.app):
            ready.set()
            await stop.wait()

    monkeypatch.setattr(server, "_prewarm_with_shutdown", initialize)
    monkeypatch.setattr(server, "_background_prewarm", AsyncMock())
    monkeypatch.setattr("y.time.check_node_async", AsyncMock(return_value=None))
    task = asyncio.create_task(serve())
    try:
        await asyncio.wait_for(initializing.wait(), 1)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            before = await client.get("/health")
            assert before.status_code == 503
            initialized.set()
            await asyncio.wait_for(ready.wait(), 1)
            after = await client.get("/health")
            assert after.status_code == 200
            assert after.json()["synced"] is True
    finally:
        initialized.set()
        stop.set()
        await task
