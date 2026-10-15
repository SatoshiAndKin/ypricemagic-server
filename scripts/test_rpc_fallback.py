"""Exercise the published proxy against controlled HTTP and WebSocket backends.

Run with the YPM development environment and an explicit Docker context. The
image must be the same immutable digest selected for production. No live RPCs
or transactions are used. The test creates and removes only its own container.
"""

import argparse
import asyncio
import contextlib
import json
import subprocess
import tempfile
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType, web


def block(number: int) -> dict[str, Any]:
    return {
        "number": hex(number),
        "hash": "0x" + f"{number:064x}",
        "parentHash": "0x" + f"{number - 1:064x}",
        "timestamp": hex(int(time.time())),
        "nonce": "0x0000000000000000",
        "sha3Uncles": "0x" + "00" * 32,
        "logsBloom": "0x" + "00" * 256,
        "transactionsRoot": "0x" + "00" * 32,
        "stateRoot": "0x" + "00" * 32,
        "receiptsRoot": "0x" + "00" * 32,
        "miner": "0x" + "00" * 20,
        "difficulty": "0x0",
        "totalDifficulty": "0x0",
        "extraData": "0x",
        "size": "0x200",
        "gasLimit": "0x1c9c380",
        "gasUsed": "0x0",
        "transactions": [],
        "uncles": [],
        "mixHash": "0x" + "00" * 32,
        "baseFeePerGas": "0x1",
    }


class Backend:
    def __init__(self, marker: str) -> None:
        self.marker = marker
        self.online = True
        self.http_ok = True
        self.events = True
        self.number = 100
        self.sockets: set[web.WebSocketResponse] = set()
        self.calls: list[dict[str, Any]] = []

    def reply(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(request)
        method = request["method"]
        response = {"jsonrpc": "2.0", "id": request["id"]}
        if method == "eth_chainId":
            result: Any = "0x1"
        elif method == "eth_blockNumber":
            result = hex(self.number)
        elif method in ("eth_getBlockByNumber", "eth_getBlockByHash"):
            value = request.get("params", ["latest"])[0]
            number = self.number if value in ("latest", "safe", "finalized") else int(value, 16)
            result = block(number)
        elif method == "eth_call" and request["params"][0].get("data") == "0xdead":
            return response | {
                "error": {"code": 3, "message": "execution reverted", "data": "0xdeadbeef"}
            }
        elif method in ("eth_getBalance", "eth_call"):
            result = "0x42"
        elif method == "eth_syncing":
            result = False
        else:
            result = self.marker
        return response | {"result": result}

    async def handle(self, request: web.Request) -> web.StreamResponse:
        if not self.online:
            raise web.HTTPServiceUnavailable()
        if request.headers.get("Upgrade", "").lower() == "websocket":
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            self.sockets.add(socket)
            try:
                async for message in socket:
                    if message.type == WSMsgType.TEXT:
                        body = json.loads(message.data)
                        if body["method"] == "eth_subscribe":
                            reply = {"jsonrpc": "2.0", "id": body["id"], "result": "0x1"}
                        else:
                            reply = self.reply(body)
                        await socket.send_json(reply)
            finally:
                self.sockets.discard(socket)
            return socket
        if not self.http_ok:
            raise web.HTTPServiceUnavailable()
        body = await request.json()
        return web.json_response(
            [self.reply(r) for r in body] if isinstance(body, list) else self.reply(body)
        )

    async def head(self, number: int) -> None:
        if not self.online or not self.events:
            return
        self.number = number
        for socket in tuple(self.sockets):
            if not socket.closed:
                await socket.send_json(
                    {
                        "jsonrpc": "2.0",
                        "method": "eth_subscription",
                        "params": {"subscription": "0x1", "result": block(number)},
                    }
                )

    async def disconnect(self) -> None:
        self.online = False
        for socket in tuple(self.sockets):
            await socket.close()


def test_config(directory: Path, ports: list[int]) -> Path:
    config = tomllib.loads((Path(__file__).resolve().parents[1] / "rpc/ethereum.toml").read_text())
    # Preserve production policy; replace only transport addresses.
    source = (Path(__file__).resolve().parents[1] / "rpc/ethereum.toml").read_text()
    for key, port in zip(("nuc", "lambo"), ports, strict=True):
        for scheme, field in (("http", "http_url"), ("ws", "ws_url")):
            source = source.replace(
                config["balanced_rpcs"][key][field],
                f"{scheme}://host.docker.internal:{port}",
            )
    path = directory / "proxy.toml"
    path.write_text(source)
    return path


async def wait_unhealthy(client: ClientSession, url: str) -> None:
    deadline = time.monotonic() + 75
    while True:
        async with client.get(url + "/health") as response:
            if response.status != 200:
                return
        assert time.monotonic() < deadline, (
            "Outage health stayed OK after all request transports failed"
        )
        await asyncio.sleep(1)


async def exercise(context: str, image: str) -> None:
    docker = ["docker", "--context", context]
    name = "ypm-fallback-test-" + uuid.uuid4().hex[:10]
    nodes = [Backend("0x11"), Backend("0x22")]
    nodes[0].online = False
    runners = []
    ports = []
    for backend in nodes:
        app = web.Application()
        app.router.add_route("*", "/", backend.handle)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        ports.append(runner.addresses[0][1])
        runners.append(runner)
    try:
        with tempfile.TemporaryDirectory(
            prefix="rpc-fallback-", dir=Path(__file__).resolve().parents[1]
        ) as directory:
            path = test_config(Path(directory), ports)
            await asyncio.to_thread(
                subprocess.run,
                [
                    *docker,
                    "create",
                    "--name",
                    name,
                    "--platform",
                    "linux/amd64",
                    "--memory",
                    "512m",
                    "--memory-swap",
                    "512m",
                    "--cpus",
                    "1",
                    "-p",
                    "127.0.0.1::8544",
                    image,
                    "--workers",
                    "2",
                    "--config",
                    "/tmp/proxy.toml",
                    "proxyd",
                    "--port",
                    "8544",
                ],
                check=True,
                capture_output=True,
            )
            await asyncio.to_thread(
                subprocess.run,
                [*docker, "cp", str(path), name + ":/tmp/proxy.toml"],
                check=True,
                capture_output=True,
            )
            await asyncio.to_thread(
                subprocess.run,
                [*docker, "start", name],
                check=True,
                capture_output=True,
            )
            binding = await asyncio.to_thread(
                subprocess.check_output, [*docker, "port", name, "8544"], text=True
            )
            url = "http://" + binding.strip()
            async with ClientSession(timeout=ClientTimeout(total=15)) as client:

                async def rpc(method: str, params: list[Any] | None = None) -> dict[str, Any]:
                    async with client.post(
                        url,
                        json={
                            "jsonrpc": "2.0",
                            "id": "request-id",
                            "method": method,
                            "params": params or [],
                        },
                    ) as response:
                        return await response.json()

                async def marker(expected: str, seconds: int = 90) -> None:
                    deadline = time.monotonic() + seconds
                    while time.monotonic() < deadline:
                        with contextlib.suppress(ClientError, TimeoutError):
                            reply = await rpc("eth_gasPrice")
                            if reply.get("result") == expected:
                                assert reply["id"] == "request-id"
                                print(f"PASS backend={expected}", flush=True)
                                return
                        await asyncio.sleep(1)
                    raise AssertionError(f"Backend did not become {expected}")

                async def heads() -> None:
                    number = 101
                    while True:
                        await asyncio.gather(*(node.head(number) for node in nodes))
                        number += 1
                        await asyncio.sleep(1)

                pump = asyncio.create_task(heads())
                try:
                    await marker("0x22")  # Cold start while primary is offline.
                    async with client.get(url + "/health") as response:
                        assert response.status == 200
                    nodes[0].online = True
                    await marker("0x11")
                    nodes[0].http_ok = False
                    await marker("0x22")  # HTTP failure with healthy WS heads.
                    nodes[0].http_ok = True
                    await marker("0x11")
                    nodes[0].events = False
                    await marker("0x22")  # Lost/stale heads while HTTP stays up.
                    nodes[0].events = True
                    await marker("0x11")
                    await nodes[0].disconnect()
                    await marker("0x22")
                    nodes[0].online = True
                    await marker("0x11")
                    payload = [
                        {
                            "jsonrpc": "2.0",
                            "id": identity,
                            "method": "eth_getBalance",
                            "params": ["0x" + "11" * 20, "0x10"],
                        }
                        for identity in (7, "batch-id")
                    ]
                    async with client.post(url, json=payload) as response:
                        batch = await response.json()
                    assert {r["id"] for r in batch} == {7, "batch-id"}
                    assert all(r["result"] == "0x42" for r in batch)
                    assert await rpc("eth_getBalance", ["0x" + "11" * 20, "0x10"]) == {
                        "jsonrpc": "2.0",
                        "id": "request-id",
                        "result": "0x42",
                    }
                    revert = await rpc(
                        "eth_call", [{"to": "0x" + "11" * 20, "data": "0xdead"}, "0x10"]
                    )
                    assert (
                        revert["id"] == "request-id"
                        and revert["error"]["code"] == 3
                        and revert["error"]["data"] == "0xdeadbeef"
                    )
                    assert any(
                        c["method"] == "eth_getBalance" and c["params"][-1] == "0x10"
                        for c in nodes[0].calls
                    )
                    print("PASS batch IDs, historical block, contract revert", flush=True)
                    await asyncio.gather(*(node.disconnect() for node in nodes))
                    await wait_unhealthy(client, url)
                    reply = await rpc("eth_gasPrice")
                    assert "error" in reply
                    print("PASS both backends unavailable", flush=True)
                finally:
                    pump.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await pump
    except BaseException:
        await asyncio.to_thread(
            subprocess.run, [*docker, "logs", "--tail", "70", name], check=False
        )
        raise
    finally:
        await asyncio.to_thread(
            subprocess.run, [*docker, "rm", "-f", name], check=False, capture_output=True
        )
        for runner in runners:
            await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    asyncio.run(exercise(args.context, args.image))
