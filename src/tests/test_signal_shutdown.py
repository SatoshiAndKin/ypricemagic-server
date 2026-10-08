"""Exercise Uvicorn's real process signal handlers and lifespan."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

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
