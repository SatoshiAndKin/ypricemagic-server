"""Bound request work without making timeout responses wait for cancellation."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi.responses import JSONResponse
from starlette._utils import get_route_path
from starlette.types import ASGIApp, Receive, Scope, Send

T = TypeVar("T")


class OverloadedError(Exception):
    """No lookup capacity is available."""


class LookupSupervisor:
    """Own lookup tasks and retain their slot until cleanup actually finishes."""

    def __init__(self, active: int = 2, queued: int = 32) -> None:
        self.loop = asyncio.get_running_loop()
        self.slots = asyncio.Semaphore(active)
        self.max_queued = queued
        self.queued = 0
        self.tasks: set[asyncio.Task[Any]] = set()
        self.closing = False

    async def run(self, work: Callable[[], Awaitable[T]]) -> T:
        if self.closing or (self.slots.locked() and self.queued >= self.max_queued):
            raise OverloadedError("Price lookup queue is full or draining")
        self.queued += 1
        try:
            await self.slots.acquire()
        finally:
            self.queued -= 1
        if self.closing:
            self.slots.release()
            raise OverloadedError("Price lookup backend is draining")

        async def execute() -> T:
            return await work()

        task = self.loop.create_task(execute())
        self.tasks.add(task)
        task.add_done_callback(self._finished)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            task.cancel()
            raise

    def _finished(self, task: asyncio.Task[Any]) -> None:
        self.tasks.discard(task)
        self.slots.release()
        if not task.cancelled():
            task.exception()  # Observe failures even after the client has left.

    def cancel(self) -> None:
        self.closing = True
        for task in self.tasks:
            task.cancel()

    async def close(self) -> None:
        self.cancel()
        if self.tasks:
            await asyncio.wait(self.tasks, timeout=5)


class DeadlineMiddleware:
    """One budget around routing, block resolution, queueing, retries and metadata."""

    def __init__(self, app: ASGIApp, timeout: Callable[[], float]) -> None:
        self.app = app
        self.timeout = timeout
        self.tasks: set[asyncio.Task[None]] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or get_route_path(scope) not in (
            "/price",
            "/prices",
            "/check_bucket",
        ):
            await self.app(scope, receive, send)
            return
        budget = self.timeout()
        # Buffer the (small JSON) response until work completes so timeout cannot
        # send a second response after a partially written successful response.
        messages: list[Any] = []

        async def collect(message: Any) -> None:
            messages.append(message)

        disconnected = asyncio.Event()

        incoming: asyncio.Queue[Any] = asyncio.Queue(maxsize=1)

        async def client_receive() -> Any:
            return await incoming.get()

        async def execute() -> None:
            await self.app(scope, client_receive, collect)

        task = asyncio.create_task(execute())
        self.tasks.add(task)
        task.add_done_callback(self._finished)
        waiter = asyncio.create_task(_watch_client(receive, incoming, disconnected))
        try:
            done, _ = await asyncio.wait(
                (task, waiter), timeout=budget, return_when=asyncio.FIRST_COMPLETED
            )
            if task in done:
                await task
                for message in messages:
                    await send(message)
            else:
                task.cancel()
                if not disconnected.is_set():
                    request_id = scope.get("state", {}).get("request_id")
                    response = JSONResponse(
                        status_code=504,
                        headers={"X-Request-ID": request_id} if request_id else None,
                        content={"error": f"Price lookup timed out after {budget:.0f} seconds"},
                    )
                    await response(scope, receive, send)
        except asyncio.CancelledError:
            task.cancel()
            raise
        finally:
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)

    def _finished(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if not task.cancelled():
            task.exception()


async def _watch_client(
    receive: Receive, incoming: asyncio.Queue[Any], disconnected: asyncio.Event
) -> None:
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            disconnected.set()
            if incoming.full():
                incoming.get_nowait()
            incoming.put_nowait(message)
            return
        await incoming.put(message)
