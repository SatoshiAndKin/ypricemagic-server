"""Exercise Uvicorn's real process signal handlers and lifespan."""

import os
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest


@pytest.mark.parametrize("phase", ["warmup", "ready"])
def test_real_sigterm_aborts_warmup_or_drains_ready_server(tmp_path: Path, phase: str) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    script = tmp_path / "serve.py"
    script.write_text("""
import asyncio, runpy, sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest, uvicorn
mocks = pytest.MonkeyPatch()
fixtures = runpy.run_path("src/tests/conftest.py")
fixtures["mock_y_module"].__wrapped__(mocks)
from src import server
for name in ("compound", "chainlink", "aave", "balancer", "gearbox"):
    mocks.setattr(server, "_prewarm_" + name, AsyncMock())
async def required():
    print("warmup_entered", flush=True)
    if sys.argv[1] == "warmup":
        await asyncio.Event().wait()
async def uniswap():
    print("background_started", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        print("background_stopped", flush=True)
sys.modules["y.prices.stable_swap.curve"].curve = SimpleNamespace(_done=True, __coin_to_pools__=required())
mocks.setattr(server, "_prewarm_uniswap", uniswap)
uvicorn.run(server.app, host="127.0.0.1", port=int(sys.argv[2]), timeout_graceful_shutdown=2)
""")
    log = tmp_path / "server.log"
    with log.open("w") as stream:
        process = subprocess.Popen(
            [sys.executable, str(script), phase, str(port)],
            stdout=stream,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONPATH": str(Path.cwd()), "SENTRY_DSN": ""},
        )
        try:
            marker = "warmup_entered" if phase == "warmup" else "Application startup complete"
            deadline = time.monotonic() + 10
            while marker not in log.read_text():
                assert process.poll() is None, log.read_text()
                assert time.monotonic() < deadline, log.read_text()
                time.sleep(0.01)
            started = time.monotonic()
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=5)
            assert time.monotonic() - started < 5
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    text = log.read_text()
    assert "shutdown_signal_received" in text
    if phase == "warmup":
        assert "server_ready" not in text
        assert "Application startup complete" not in text
        assert "shutdown during required warmup" in text
    else:
        assert "server_ready" in text
        assert "background_started" in text
        assert "background_stopped" in text
        assert "Application shutdown complete" in text


@pytest.mark.parametrize("finish", [True, False], ids=["finish-accepted", "bound-shutdown"])
def test_real_sigterm_preserves_active_and_queued_prices(tmp_path: Path, finish: bool) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    script = tmp_path / "serve_prices.py"
    script.write_text("""
import asyncio, runpy, sys
from pathlib import Path
from unittest.mock import AsyncMock
import pytest, uvicorn
mocks = pytest.MonkeyPatch()
runpy.run_path("src/tests/conftest.py")["mock_y_module"].__wrapped__(mocks)
from src import server
for name in ("compound", "chainlink", "aave", "balancer", "gearbox", "uniswap"):
    mocks.setattr(server, "_prewarm_" + name, AsyncMock())
release = Path(sys.argv[2])
async def lookup(*args, **kwargs):
    print("lookup_entered", flush=True)
    try:
        while not release.exists():
            await asyncio.sleep(0.01)
        return (1.25, None, 1234567890)
    finally:
        print("lookup_stopped", flush=True)
mocks.setattr(server, "_fetch_price_and_cache", lookup)
async def track_queue():
    while server.app.state.lookups.queued < 1:
        await asyncio.sleep(0.01)
    print("request_queued", flush=True)
original_run = server.LookupSupervisor.run
async def tracked_run(self, work):
    asyncio.create_task(track_queue())
    return await original_run(self, work)
mocks.setattr(server.LookupSupervisor, "run", tracked_run)
uvicorn.run(server.app, host="127.0.0.1", port=int(sys.argv[1]), timeout_graceful_shutdown=1)
""")
    log, release = tmp_path / "server.log", tmp_path / "release"

    def wait_for(marker: str) -> None:
        deadline = time.monotonic() + 10
        while marker not in log.read_text():
            assert process.poll() is None, log.read_text()
            assert time.monotonic() < deadline, log.read_text()
            time.sleep(0.01)

    def price(index: int) -> httpx.Response:
        return httpx.get(
            f"http://127.0.0.1:{port}/price",
            params={"token": f"0x{index:040x}", "block": "19000000"},
            timeout=10,
        )

    with log.open("w") as stream, ThreadPoolExecutor(max_workers=3) as clients:
        process = subprocess.Popen(
            [sys.executable, str(script), str(port), str(release)],
            stdout=stream,
            stderr=subprocess.STDOUT,
            env={
                **os.environ,
                "PYTHONPATH": str(Path.cwd()),
                "SENTRY_DSN": "",
                "CACHE_DIR": str(tmp_path / "prices"),
            },
        )
        try:
            wait_for("Application startup complete")
            requests = [clients.submit(price, index) for index in range(1, 4)]
            wait_for("request_queued")
            assert log.read_text().count("lookup_entered") == 2
            process.send_signal(signal.SIGTERM)
            wait_for("shutdown_signal_received")
            if finish:
                # Release only after Uvicorn begins its real connection drain.
                wait_for("Waiting for connections to close")
                assert process.poll() is None
                release.touch()
            responses = [request.result(timeout=10) for request in requests]
            process.wait(timeout=5)
            if finish:
                assert [response.status_code for response in responses] == [200, 200, 200]
                assert [response.json()["price"] for response in responses] == [1.25] * 3
            else:
                assert all(response.status_code == 500 for response in responses)
                assert "timeout graceful shutdown exceeded" in log.read_text()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    assert "Application shutdown complete" in log.read_text()
