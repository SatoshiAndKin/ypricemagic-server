"""Release regressions exercised through production request routing."""

import asyncio
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.responses import JSONResponse

from src import cache, server

TOKEN = "0x6B175474E89094C44Da98b954EedeAC495271d0F"


async def request(root_path: str = "") -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app, root_path=root_path), base_url="http://test"
    ) as client:
        return await client.get(
            root_path + "/price", params={"token": TOKEN, "block": 18000000, "amount": "1"}
        )


@pytest.mark.parametrize("root_path", ["", "/ethereum", "/base"])
async def test_deadline_responds_before_slow_cancellation(
    monkeypatch: pytest.MonkeyPatch, root_path: str
) -> None:
    monkeypatch.setattr(server, "PRICE_TIMEOUT", 0.04)
    cancelled, released = asyncio.Event(), asyncio.Event()

    async def slow(*args: object, **kwargs: object) -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            await released.wait()
            raise

    with patch("y.get_price", slow):
        task = asyncio.create_task(request(root_path))
        try:
            response = await asyncio.wait_for(asyncio.shield(task), 0.15)
            assert response.status_code == 504
            await asyncio.wait_for(cancelled.wait(), 0.1)
        finally:
            released.set()
            await task


async def test_timeout_is_attempted_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "PRICE_TIMEOUT", 0.04)
    lookup = AsyncMock(side_effect=TimeoutError("provider timeout"))
    with patch("y.get_price", lookup):
        started = time.monotonic()
        response = await request()
    assert response.status_code == 504
    assert lookup.await_count == 1
    assert time.monotonic() - started < 0.15


async def test_transient_failure_never_enters_not_found_cache() -> None:
    with (
        patch("y.get_price", AsyncMock(side_effect=TimeoutError("RPC timeout"))),
        patch("src.server.get_cached_price", return_value=None),
        patch("src.server.get_cached_error", return_value=None),
        patch("src.server.set_cached_error") as write,
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.get("/price", params={"token": TOKEN, "block": 18000000})
    assert response.status_code == 504
    write.assert_not_called()


def test_legacy_ambiguous_error_is_a_cache_miss(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    cache.close_cache()
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
    cache.get_cache().set(cache.make_key(TOKEN, 18000000), {"error": "RPC timeout"})
    assert cache.get_cached_error(TOKEN, 18000000) is None
    cache.close_cache()


async def test_cancelled_warmup_aborts_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    shutdown = asyncio.Event()
    started, stopped = asyncio.Event(), asyncio.Event()

    async def slow() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(server, "_shutdown_event", shutdown)
    for name in ("uniswap", "compound", "chainlink", "aave", "balancer", "gearbox"):
        monkeypatch.setattr(server, f"_prewarm_{name}", AsyncMock())
    task = asyncio.create_task(
        server._prewarm_with_shutdown(SimpleNamespace(_done=True, __coin_to_pools__=slow()))
    )
    await started.wait()
    shutdown.set()
    with pytest.raises(RuntimeError, match="shutdown"):
        await task
    assert stopped.is_set()


async def test_overload_keeps_cached_requests_and_health_responsive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.runtime import LookupSupervisor

    supervisor = LookupSupervisor()
    monkeypatch.setattr(server.app.state, "lookups", supervisor, raising=False)
    entered, release = asyncio.Event(), asyncio.Event()
    active = 0

    async def lookup(*args: object, **kwargs: object) -> float:
        nonlocal active
        active += 1
        if active == 2:
            entered.set()
        await release.wait()
        active -= 1
        return 1.0

    with (
        patch("y.get_price", lookup),
        patch("y.get_block_timestamp_async", AsyncMock(return_value=1700000000)),
        patch("y.time.check_node_async", AsyncMock()),
        patch(
            "src.server.get_cached_price",
            return_value={"price": 1.0, "block_timestamp": 1700000000},
        ),
    ):
        running = [asyncio.create_task(request()) for _ in range(34)]
        await entered.wait()
        while supervisor.queued < 32:
            await asyncio.sleep(0)
        try:
            overloaded = await request()
            assert overloaded.status_code == 503
            assert overloaded.headers["Retry-After"] == "5"
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=server.app), base_url="http://test"
            ) as client:
                cached = await client.get("/price", params={"token": TOKEN, "block": 18000000})
                health = await client.get("/health")
            assert cached.status_code == health.status_code == 200
            assert cached.json()["cached"] is True
        finally:
            release.set()
            responses = await asyncio.gather(*running)
        assert [response.status_code for response in responses] == [200] * 34
        assert active == supervisor.queued == 0
        assert not supervisor.tasks


async def test_queue_wait_counts_toward_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.runtime import LookupSupervisor

    supervisor = LookupSupervisor(active=1, queued=32)
    monkeypatch.setattr(server.app.state, "lookups", supervisor, raising=False)
    monkeypatch.setattr(server, "PRICE_TIMEOUT", 0.04)
    await supervisor.slots.acquire()
    lookup = AsyncMock(return_value=1)
    with patch("y.get_price", lookup):
        response = await request()
    assert response.status_code == 504
    for _ in range(20):
        await asyncio.sleep(0)
    assert supervisor.queued == 0
    lookup.assert_not_called()
    supervisor.slots.release()


async def test_latest_block_resolution_uses_the_same_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "PRICE_TIMEOUT", 0.04)
    entered = asyncio.Event()

    async def slow_head() -> int:
        entered.set()
        await asyncio.Event().wait()
        return 18000000

    monkeypatch.setattr(server, "_head_block", slow_head)
    with patch("y.get_price", AsyncMock()) as lookup:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app, root_path="/ethereum"),
            base_url="http://test",
        ) as client:
            response = await client.get("/ethereum/price", params={"token": TOKEN})
        assert entered.is_set()
        assert response.status_code == 504
        lookup.assert_not_called()


@pytest.mark.parametrize("endpoint", ["price", "prices"])
@pytest.mark.parametrize(
    "error,status", [(TimeoutError("RPC timeout"), 504), (ConnectionError("RPC unavailable"), 502)]
)
async def test_block_resolution_preserves_transient_status(
    monkeypatch: pytest.MonkeyPatch, endpoint: str, error: Exception, status: int
) -> None:
    monkeypatch.setattr(server, "_head_block", AsyncMock(side_effect=error))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/" + endpoint, params={"token" if endpoint == "price" else "tokens": TOKEN}
        )
    assert response.status_code == status


@pytest.mark.parametrize("state", ["starting", "draining", "stopped"])
async def test_health_unavailable_outside_readiness(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    monkeypatch.setattr(server.app.state, "ready", state == "draining")
    if state == "draining":
        server._shutdown_event.set()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


async def test_client_disconnect_cancels_owned_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    stopped, entered, disconnected = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def lookup(*args: object, **kwargs: object) -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    first = True

    async def receive() -> Any:
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    messages: list[object] = []

    async def send(message: object) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/price",
        "raw_path": b"/price",
        "query_string": f"token={TOKEN}&block=18000000&amount=1".encode(),
        "root_path": "",
        "headers": [],
        "server": ("test", 80),
        "client": ("test", 123),
    }
    monkeypatch.setattr(server, "PRICE_TIMEOUT", 0.2)
    with patch("y.get_price", lookup):
        task = asyncio.create_task(server.app(scope, receive, send))
        await entered.wait()
        disconnected.set()
        await asyncio.wait_for(stopped.wait(), 0.1)
        await task
    assert messages == []


async def test_required_initialization_precedes_owned_background_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = asyncio.Event()
    warming = asyncio.Event()
    stopped = asyncio.Event()
    shutdown = asyncio.Event()
    monkeypatch.setattr(server, "_shutdown_event", shutdown)

    async def initialize(registry: Any) -> None:
        assert server.app.state.ready is False
        assert not warming.is_set()
        initialized.set()

    async def background() -> None:
        assert initialized.is_set()
        warming.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(server, "_prewarm_with_shutdown", initialize)
    monkeypatch.setattr(server, "_background_prewarm", background)
    async with server.lifespan(server.app):
        await warming.wait()
        assert server.app.state.ready is True
        assert not server.app.state.warmup.done()
        server._signal_shutdown_handler()
        response = await server.health()
        assert isinstance(response, JSONResponse)
        assert response.status_code == 503
    assert stopped.is_set()
    assert server.app.state.ready is False
    assert server.app.state.warmup.done()


@pytest.mark.parametrize("endpoint", ["price", "prices"])
@pytest.mark.parametrize(
    "error,status", [(TimeoutError("RPC timeout"), 504), (ConnectionError("RPC unavailable"), 502)]
)
async def test_timestamp_resolution_preserves_transient_status(
    monkeypatch: pytest.MonkeyPatch, endpoint: str, error: Exception, status: int
) -> None:
    monkeypatch.setattr(server, "_resolve_block_from_timestamp", AsyncMock(side_effect=error))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/" + endpoint,
            params={"token" if endpoint == "price" else "tokens": TOKEN, "timestamp": "1734789347"},
        )
    assert response.status_code == status
