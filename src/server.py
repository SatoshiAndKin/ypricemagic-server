import asyncio
import logging
import math
import os
import signal
import time
import uuid
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import TYPE_CHECKING, Any

import sentry_sdk
import structlog
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.cache import (
    close_cache,
    get_cached_error,
    get_cached_price,
    set_cached_error,
    set_cached_price,
)
from src.logger import configure_logging, get_logger, sanitize_error_message
from src.params import (
    ParseError,
    is_valid_address,
    parse_batch_params,
    parse_price_params,
)

if TYPE_CHECKING:
    from src.params import BatchParams

configure_logging()
logger = get_logger("server")

_shutdown_event = asyncio.Event()


def _signal_shutdown_handler() -> None:
    """Called by the event loop when SIGTERM/SIGINT is received during prewarm."""
    logger.info("shutdown_signal_received")
    _shutdown_event.set()


class _HealthAccessFilter(logging.Filter):
    """Drop uvicorn access-log lines for successful /health requests."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ("/health" in msg and (" 200 " in msg or '"200"' in msg))


CHAIN_NAME = os.environ.get("CHAIN_NAME", "ethereum")

try:
    _VERSION = _pkg_version("ypricemagic-server")
except PackageNotFoundError:
    _VERSION = "dev"

PRICE_TIMEOUT = 300.0

# Prometheus metrics
price_requests_total = Counter(
    "price_requests_total",
    "Total price requests",
    ["chain", "status"],
)
price_request_duration_seconds = Histogram(
    "price_request_duration_seconds",
    "Price request duration",
    ["chain"],
)
batch_requests_total = Counter(
    "batch_requests_total",
    "Total batch pricing requests",
    ["chain", "status"],
)
batch_request_duration_seconds = Histogram(
    "batch_request_duration_seconds",
    "Batch request duration",
    ["chain"],
)
check_bucket_requests_total = Counter(
    "check_bucket_requests_total",
    "Total check_bucket requests",
    ["chain", "status"],
)
check_bucket_request_duration_seconds = Histogram(
    "check_bucket_request_duration_seconds",
    "Check bucket request duration",
    ["chain"],
)

# Per-token classification lock — deduplicates concurrent check_bucket calls
# for the same token address so ypricemagic only classifies once.
# Note: grows one entry per unique token address, never cleaned up.
# This is acceptable — locks are lightweight and the set of queried tokens is bounded.
_bucket_locks: dict[str, asyncio.Lock] = {}
_bucket_locks_guard = asyncio.Lock()


async def _get_token_lock(token: str) -> asyncio.Lock:
    """Get or create a per-token lock. Thread-safe via _bucket_locks_guard."""
    async with _bucket_locks_guard:
        if token not in _bucket_locks:
            _bucket_locks[token] = asyncio.Lock()
        return _bucket_locks[token]


async def _prewarm_uniswap() -> None:
    """Pre-load Uniswap V2/V3 pool indexes concurrently.

    Each sub-step is wrapped in try/except so partial failures don't prevent startup.
    All routers (V2, V3, V3 forks) load in parallel for faster startup.
    """
    from y.prices.dex.uniswap import uniswap_multiplexer  # type: ignore[attr-defined]

    async def _load_v2(name: str, router: Any) -> None:
        try:
            logger.info("uniswap_v2_pools_loading_started", router=name)
            await router.__pools__
            logger.info("uniswap_v2_pools_loading_done", router=name)
        except Exception as v2_err:
            logger.warning("uniswap_prewarm_failed", router=name, version="v2", error=str(v2_err))

    async def _load_v3() -> None:
        try:
            logger.info("uniswap_v3_pools_loading_started")
            await uniswap_multiplexer.v3.__pools__  # type: ignore[union-attr]
            logger.info("uniswap_v3_pools_loading_done")
        except Exception as v3_err:
            logger.warning("uniswap_prewarm_failed", version="v3", error=str(v3_err))

    async def _load_v3_fork(fork: Any) -> None:
        try:
            logger.info("uniswap_v3_pools_loading_started", fork=str(fork))
            await fork.__pools__
            logger.info("uniswap_v3_pools_loading_done", fork=str(fork))
        except Exception as v3_fork_err:
            logger.warning(
                "uniswap_prewarm_failed",
                version="v3_fork",
                fork=str(fork),
                error=str(v3_fork_err),
            )

    tasks: list[Any] = [
        _load_v2(name, router) for name, router in uniswap_multiplexer.v2_routers.items()
    ]
    if uniswap_multiplexer.v3:
        tasks.append(_load_v3())
    for fork in uniswap_multiplexer.v3_forks:
        tasks.append(_load_v3_fork(fork))

    await asyncio.gather(*tasks, return_exceptions=True)


async def _prewarm_compound() -> None:
    """Pre-load Compound-like comptroller markets so first price request is fast."""
    try:
        from y.prices.lending.compound import Comptroller, compound

        if not compound or not hasattr(compound, "trollers"):
            return
        logger.info("compound_markets_loading_started", comptrollers=len(compound.trollers))
        # Load all comptroller market lists in parallel using a_sync's map API
        trollers = compound.trollers.values()
        async for troller, markets in Comptroller.markets.map(trollers):  # type: ignore[arg-type,var-annotated]
            logger.debug("compound_troller_loaded", troller=str(troller), markets=len(markets))
        logger.info("compound_markets_loading_done")
    except Exception as e:
        logger.warning("compound_prewarm_failed", error=str(e))


async def _prewarm_chainlink() -> None:
    """Pre-load Chainlink FeedConfirmed events so first has_feed() call is fast."""
    try:
        from y.prices.chainlink import chainlink

        if not chainlink or not hasattr(chainlink, "_feeds_from_events"):
            return
        if chainlink._feeds_from_events is None:
            return
        import dank_mids

        logger.info("chainlink_feeds_loading_started")
        # Trigger the event scan by iterating feeds up to current block
        async for _ in chainlink._feeds_thru_block(await dank_mids.eth.block_number):  # type: ignore[attr-defined]
            pass
        logger.info("chainlink_feeds_loading_done")
    except Exception as e:
        logger.warning("chainlink_prewarm_failed", error=str(e))


async def _prewarm_aave() -> None:
    """Pre-load Aave pool registries (V1/V2/V3) in parallel."""
    try:
        from y.prices.lending.aave import aave

        logger.info("aave_pools_loading_started")
        await aave.__pools__
        logger.info("aave_pools_loading_done")
    except Exception as e:
        logger.warning("aave_prewarm_failed", error=str(e))


async def _prewarm_balancer() -> None:
    """Pre-load Balancer V1/V2 version objects."""
    try:
        from y.prices.dex.balancer.balancer import balancer_multiplexer

        logger.info("balancer_loading_started")
        await balancer_multiplexer.__versions__
        logger.info("balancer_loading_done")
    except Exception as e:
        logger.warning("balancer_prewarm_failed", error=str(e))


async def _prewarm_gearbox() -> None:
    """Pre-load Gearbox diesel pools (mainnet only)."""
    try:
        from y.prices.gearbox import gearbox

        if not gearbox or isinstance(gearbox, set):
            return
        logger.info("gearbox_loading_started")
        await gearbox.diesel_tokens()
        logger.info("gearbox_loading_done")
    except Exception as e:
        logger.warning("gearbox_prewarm_failed", error=str(e))


async def _prewarm_with_shutdown(curve_registry: Any) -> None:
    """Run all prewarm tasks in parallel, cancelling immediately on shutdown signal."""

    async def _prewarm_curve() -> None:
        if curve_registry and hasattr(curve_registry, "_done"):
            logger.info("curve_registry_loading_started")
            _ = curve_registry._done
            await curve_registry.__coin_to_pools__
            logger.info("curve_registry_loading_done")

    prewarm_tasks: list[asyncio.Task[None]] = [
        asyncio.create_task(_prewarm_curve()),
        asyncio.create_task(_prewarm_uniswap()),
        asyncio.create_task(_prewarm_compound()),
        asyncio.create_task(_prewarm_chainlink()),
        asyncio.create_task(_prewarm_aave()),
        asyncio.create_task(_prewarm_balancer()),
        asyncio.create_task(_prewarm_gearbox()),
    ]

    async def _wait_for_shutdown() -> None:
        await _shutdown_event.wait()

    shutdown_waiter = asyncio.create_task(_wait_for_shutdown())

    async def _run_prewarm() -> None:
        await asyncio.gather(*prewarm_tasks, return_exceptions=True)

    prewarm_task = asyncio.create_task(_run_prewarm())
    done, _ = await asyncio.wait(
        [prewarm_task, shutdown_waiter],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if shutdown_waiter in done:
        logger.info("shutdown_during_prewarm", chain=CHAIN_NAME)
        prewarm_task.cancel()
        await asyncio.gather(prewarm_task, return_exceptions=True)
    else:
        shutdown_waiter.cancel()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    # Install after uvicorn has configured its loggers (CLI resets them at startup).
    logging.getLogger("uvicorn.access").addFilter(_HealthAccessFilter())

    # Temporarily override signal handlers so we can cancel prewarm on shutdown.
    # loop.add_signal_handler() replaces uvicorn's signal.signal() handler;
    # loop.remove_signal_handler() restores it (documented Python behaviour).
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_shutdown_handler)

    _startup_start = time.monotonic()
    logger.info("startup", chain=CHAIN_NAME)
    try:
        from brownie import network

        network_id = os.environ.get("BROWNIE_NETWORK_ID", f"{CHAIN_NAME}-custom")
        if not network.is_connected():  # type: ignore[attr-defined]
            network.connect(network_id)  # type: ignore[attr-defined]
        logger.info("brownie_connected", network_id=network_id)

        from dank_mids.helpers._helpers import setup_dank_w3_from_sync

        setup_dank_w3_from_sync(network.web3)
        logger.info("dank_mids_patched")

        from brownie import chain
        from y import get_price  # noqa: F401

        logger.info("chain_connected", chain=CHAIN_NAME, chain_id=chain.id, block=chain.height)

        # Pre-load the Curve registry at startup so the first pricing request
        # doesn't block on expensive factory event scans.
        # If a shutdown signal arrives, cancel prewarm and proceed so uvicorn
        # can shut down immediately instead of blocking for minutes.
        from y.prices.stable_swap.curve import curve as _curve_registry

        await _prewarm_with_shutdown(_curve_registry)
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise
    finally:
        # Restore uvicorn's original signal handlers so graceful shutdown works.
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)

    _startup_elapsed = time.monotonic() - _startup_start
    logger.info(
        "server_ready",
        chain=CHAIN_NAME,
        startup_seconds=round(_startup_elapsed, 2),
    )

    # Init sentry AFTER dank_mids loads -- its Cython modules are incompatible
    # with sentry's threading auto-instrumentation at import time.
    _sentry_dsn = os.environ.get("SENTRY_DSN", "")
    if _sentry_dsn:
        from sentry_sdk.integrations.threading import ThreadingIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            release=_VERSION,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
            disabled_integrations=[ThreadingIntegration()],
        )
        logger.info("sentry_initialized")

    yield

    close_cache()
    logger.info("shutdown", chain=CHAIN_NAME)


_CHAINS = ["ethereum", "arbitrum", "optimism", "base", "bsc", "polygon", "fantom"]

app = FastAPI(
    title="ypricemagic API",
    description="ERC-20 token pricing API. Returns USD prices at any historical block or timestamp. Supports single and batch lookups.",
    version=_VERSION,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    servers=[{"url": f"/{c}", "description": c} for c in _CHAINS],
)


@app.get("/docs", include_in_schema=False)
async def swagger_ui() -> Any:
    return get_swagger_ui_html(
        openapi_url="openapi.json",
        title=f"{app.title} - Swagger UI",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_ui() -> Any:
    return get_redoc_html(
        openapi_url="openapi.json",
        title=f"{app.title} - ReDoc",
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert FastAPI's default 422 validation errors to our error envelope format."""
    # Extract the first error message for a cleaner response
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        loc = " -> ".join(str(x) for x in first_error.get("loc", []))
        msg = first_error.get("msg", "Validation error")
        error_message = f"Validation error in {loc}: {msg}"
    else:
        error_message = "Validation error"
    return JSONResponse(status_code=422, content={"error": error_message})


# Expose Prometheus metrics at /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

_cors_origins_raw = os.environ.get("CORS_ORIGINS", "")
_cors_origins: list[str] = (
    [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    if _cors_origins_raw.strip()
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Any:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get(
    "/health",
    description="Check API and RPC node status. Returns chain name, latest block height, and node sync state.",
)
async def health() -> dict[str, Any]:
    try:
        from brownie import chain

        height = chain.height
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content={"status": "unhealthy", "chain": CHAIN_NAME, "error": "RPC connection failed"},
        )

    # Check node sync status
    synced: bool | None = None
    try:
        from y.time import check_node_async

        await asyncio.wait_for(check_node_async(), timeout=5.0)
        synced = True
    except TimeoutError:
        logger.warning("health_check_node_timeout")
        synced = None
    except Exception as e:
        # Check if it's NodeNotSynced by class name (avoids import issues in except block)
        if type(e).__name__ == "NodeNotSynced":
            synced = False
        else:
            logger.warning("health_check_node_error", error=str(e))
            synced = None

    return {"status": "ok", "chain": CHAIN_NAME, "block": height, "synced": synced}


def _serialize_trade_path(result: Any) -> list[dict[str, Any]] | None:
    """Extract and serialize the trade path from a PriceResult."""
    path = getattr(result, "path", None)
    if not path:
        return None
    return [
        {
            "token": step.token,
            "price": float(step.price),
            "source": step.source,
        }
        for step in path
    ]


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((ConnectionError, OSError)),
)
async def _fetch_price(
    token: str,
    block: int,
    amount: float | None = None,
    ignore_pools: tuple[str, ...] = (),
) -> tuple[float, list[dict[str, Any]] | None] | None:
    """Fetch a single token price. Returns (price, trade_path) or None."""
    from y import get_price

    kwargs: dict[str, Any] = {
        "fail_to_None": True,
        "sync": False,
    }
    if amount is not None:
        kwargs["amount"] = amount
    if ignore_pools:
        kwargs["ignore_pools"] = ignore_pools

    logger.debug("fetch_price_start", token=token, block=block, kwargs=list(kwargs.keys()))
    p = await asyncio.wait_for(get_price(token, block, **kwargs), timeout=PRICE_TIMEOUT)
    logger.debug("fetch_price_done", token=token, block=block, result_type=type(p).__name__)
    if p is None:
        return None
    price_float = float(p)
    if math.isnan(price_float) or math.isinf(price_float):
        raise ValueError(f"Invalid price value {p} for {token} at block {block}")
    if price_float < 0:
        raise ValueError(f"Negative price {price_float} for {token} at block {block}")
    trade_path = _serialize_trade_path(p)
    return price_float, trade_path


async def _fetch_price_and_cache(
    token: str,
    block: int,
    amount: float | None = None,
    ignore_pools: tuple[str, ...] = (),
) -> tuple[float, list[dict[str, Any]] | None, int | None] | None:
    """Fetch price, timestamp, and write cache in one shieldable coroutine."""
    result = await _fetch_price(token, block, amount=amount, ignore_pools=ignore_pools)
    if result is None:
        return None
    price_float, trade_path = result
    block_timestamp = await _fetch_block_timestamp(block)
    if amount is None:
        set_cached_price(token, block, price_float, block_timestamp=block_timestamp)
    return price_float, trade_path, block_timestamp


async def _fetch_batch_prices(
    tokens: tuple[str, ...],
    block: int,
    amounts: tuple[float | None, ...] | None = None,
) -> list[tuple[float, list[dict[str, Any]] | None] | None]:
    """Fetch prices for multiple tokens in parallel.

    Returns a list of (price, trade_path) tuples or None for tokens that couldn't be priced.
    Does not raise exceptions - errors are logged and None is returned for that token.
    """
    from y import get_prices

    kwargs: dict[str, Any] = {
        "fail_to_None": True,
        "sync": False,
    }
    if amounts is not None:
        kwargs["amounts"] = amounts

    try:
        results = await asyncio.wait_for(get_prices(tokens, block, **kwargs), timeout=PRICE_TIMEOUT)
        prices: list[tuple[float, list[dict[str, Any]] | None] | None] = []
        for i, p in enumerate(results):
            if p is None:
                prices.append(None)
            else:
                price_float = float(p)
                if math.isnan(price_float) or math.isinf(price_float) or price_float < 0:
                    logger.warning(
                        "batch_invalid_price",
                        token=tokens[i],
                        block=block,
                        price=p,
                    )
                    prices.append(None)
                else:
                    trade_path = _serialize_trade_path(p)
                    prices.append((price_float, trade_path))
        return prices
    except TimeoutError:
        logger.warning("batch_fetch_timed_out", block=block)
        raise
    except Exception as e:
        logger.error("batch_fetch_failed", block=block, error=str(e))
        return [None] * len(tokens)


async def _fetch_block_timestamp(block: int) -> int | None:
    """Fetch the Unix epoch timestamp for a block.

    Returns the timestamp on success, None on failure.
    """
    try:
        from y import get_block_timestamp_async

        return await get_block_timestamp_async(block)
    except Exception as e:
        logger.warning(
            "block_timestamp_fetch_failed",
            block=block,
            error=str(e),
        )
        return None


async def _resolve_block_from_timestamp(timestamp: int) -> int:
    """Resolve a Unix timestamp to a block number.

    Raises Exception on RPC failure.
    """
    from datetime import UTC, datetime

    from y import get_block_at_timestamp

    # Convert Unix epoch to timezone-aware datetime (ypricemagic expects datetime, not int)
    dt = datetime.fromtimestamp(timestamp, tz=UTC)
    return await get_block_at_timestamp(dt, sync=False)


def _make_error_response(status: int, message: str) -> JSONResponse:
    """Create a JSON error response with sensitive data scrubbed."""
    return JSONResponse(status_code=status, content={"error": sanitize_error_message(message)})


def _make_timeout_response() -> JSONResponse:
    return _make_error_response(504, f"Price lookup timed out after {PRICE_TIMEOUT:.0f} seconds")


def _handle_price_error(e: Exception, token: str, block: int, duration_ms: int) -> JSONResponse:
    """Handle exceptions from price fetching and return appropriate response."""
    inner = e.last_attempt.exception() if isinstance(e, RetryError) else e
    msg = str(inner)
    price_requests_total.labels(chain=CHAIN_NAME, status="error").inc()
    logger.error(
        "price_lookup_failed",
        token=token,
        block=block,
        duration_ms=duration_ms,
    )
    if "Invalid price value" in msg or "Negative price" in msg:
        return _make_error_response(
            502,
            f"Price source returned invalid value for {token} at block {block}",
        )
    if isinstance(inner, TimeoutError):
        return _make_timeout_response()
    return _make_error_response(
        500,
        f"Price lookup failed for {token} at block {block}: {msg}",
    )


async def _resolve_price_block(params: Any) -> int | JSONResponse:
    from brownie import chain as brownie_chain

    if params.timestamp is None:
        block = params.block if params.block is not None else brownie_chain.height
        logger.debug("resolve_block", source="param_or_latest", block=block)
        return block

    logger.debug("resolve_block_from_timestamp", timestamp=params.timestamp)
    try:
        return await _resolve_block_from_timestamp(params.timestamp)
    except Exception as e:
        logger.error(
            "timestamp_resolution_failed",
            timestamp=params.timestamp,
            error=str(e),
        )
        return _make_error_response(
            502,
            f"Failed to resolve timestamp {params.timestamp} to block: {e}",
        )


async def _handle_price_request(params: Any, actual_block: int, force: bool = False) -> Any:
    if params.amount is None:
        cached = get_cached_price(params.token, actual_block)
        if cached is not None:
            logger.info(
                "cache_hit",
                chain=CHAIN_NAME,
                token=params.token,
                block=actual_block,
                price=cached["price"],
            )
            price_requests_total.labels(chain=CHAIN_NAME, status="cache_hit").inc()
            cached_price = float(cached["price"])  # type: ignore[arg-type]
            return {
                "token": params.token,
                "price": cached_price,
                "block": actual_block,
                "chain": CHAIN_NAME,
                "block_timestamp": cached.get("block_timestamp"),
                "cached": True,
                "trade_path": None,
            }

        # Return a cached error immediately (avoids re-fetching until TTL expires).
        # When force=True, skip this check and proceed to a real price lookup.
        if not force:
            cached_err = get_cached_error(params.token, actual_block)
            if cached_err is not None:
                logger.info(
                    "cache_error_hit",
                    chain=CHAIN_NAME,
                    token=params.token,
                    block=actual_block,
                    error=cached_err.get("error"),
                )
                price_requests_total.labels(chain=CHAIN_NAME, status="cache_error_hit").inc()
                return _make_error_response(
                    404,
                    f"No price found for {params.token} at block {actual_block} on {CHAIN_NAME} "
                    f"(cached error: {cached_err.get('error')})",
                )
        else:
            logger.info(
                "force_bypass_error_cache",
                chain=CHAIN_NAME,
                token=params.token,
                block=actual_block,
            )

    start = time.monotonic()
    try:
        fetch_result = await asyncio.shield(
            _fetch_price_and_cache(
                params.token,
                actual_block,
                amount=params.amount,
                ignore_pools=params.ignore_pools,
            )
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        # Cache the error so immediate retries are fast (TTL-limited)
        if params.amount is None:
            inner = e.last_attempt.exception() if isinstance(e, RetryError) else e
            set_cached_error(params.token, actual_block, str(inner))
        return _handle_price_error(e, params.token, actual_block, duration_ms)

    if fetch_result is None:
        price_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        logger.warning("price_not_found", token=params.token, block=actual_block)
        # Cache the "not found" outcome so repeated requests don't re-trigger lookups
        if params.amount is None:
            set_cached_error(
                params.token,
                actual_block,
                f"No price found for {params.token} at block {actual_block} on {CHAIN_NAME}",
            )
        return _make_error_response(
            404,
            f"No price found for {params.token} at block {actual_block} on {CHAIN_NAME}",
        )

    price_float, trade_path, block_timestamp = fetch_result
    duration_ms = int((time.monotonic() - start) * 1000)
    price_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
    price_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)
    logger.info(
        "price_fetched",
        chain=CHAIN_NAME,
        token=params.token,
        block=actual_block,
        price=price_float,
        amount=params.amount,
        duration_ms=duration_ms,
    )

    return {
        "token": params.token,
        "price": price_float,
        "block": actual_block,
        "chain": CHAIN_NAME,
        "block_timestamp": block_timestamp,
        "cached": False,
        "trade_path": trade_path,
    }


async def _resolve_batch_block(
    params: "BatchParams",
) -> int | tuple[int, JSONResponse]:
    """Resolve the block for batch pricing.

    Returns the block number on success.
    Returns a tuple of (0, error_response) on failure.
    """
    from brownie import chain as brownie_chain

    if params.timestamp is not None:
        try:
            return await _resolve_block_from_timestamp(params.timestamp)
        except Exception as e:
            logger.error(
                "batch_timestamp_resolution_failed",
                timestamp=params.timestamp,
                error=str(e),
            )
            return (
                0,
                _make_error_response(
                    502,
                    f"Failed to resolve timestamp {params.timestamp} to block: {e}",
                ),
            )
    return params.block if params.block is not None else brownie_chain.height


def _prepare_batch_cache_check(
    params: "BatchParams",
    block: int,
) -> tuple[list[dict[str, Any]], list[str], list[int]]:
    """Prepare batch results by checking cache for each token.

    Returns:
    - results: list of result dicts (with placeholders for tokens to fetch)
    - tokens_to_fetch: list of tokens that need fetching
    - indices_to_fetch: original indices of tokens to fetch
    """
    results: list[dict[str, Any]] = []
    tokens_to_fetch: list[str] = []
    indices_to_fetch: list[int] = []

    for i, token in enumerate(params.tokens):
        token_amount = params.amounts[i] if params.amounts is not None else None

        # Check cache only if: no amount
        if token_amount is None:
            cached = get_cached_price(token, block)
            if cached is not None:
                results.append(
                    {
                        "token": token,
                        "block": block,
                        "price": cached["price"],
                        "block_timestamp": cached.get("block_timestamp"),
                        "cached": True,
                    }
                )
                continue

        # Need to fetch this token
        tokens_to_fetch.append(token)
        indices_to_fetch.append(i)
        results.append({})  # Placeholder

    return results, tokens_to_fetch, indices_to_fetch


def _fill_batch_results(
    results: list[dict[str, Any]],
    tokens_to_fetch: list[str],
    indices_to_fetch: list[int],
    prices: list[tuple[float, list[dict[str, Any]] | None] | None],
    block: int,
    block_timestamp: int | None,
    params: "BatchParams",
) -> None:
    """Fill in batch results with fetched prices and cache them."""
    for idx, token in enumerate(tokens_to_fetch):
        i = indices_to_fetch[idx]
        price_entry = prices[idx]
        token_amount = params.amounts[i] if params.amounts is not None else None

        if price_entry is None:
            price_val = None
            trade_path = None
        else:
            price_val, trade_path = price_entry

        results[i] = {
            "token": token,
            "block": block,
            "price": price_val,
            "block_timestamp": block_timestamp,
            "cached": False,
            "trade_path": trade_path,
        }

        # Cache only if: price found AND no amount
        if price_val is not None and token_amount is None:
            set_cached_price(token, block, price_val, block_timestamp=block_timestamp)


@app.get(
    "/price",
    description="Get the USD price of an ERC-20 token at a given block or timestamp. "
    "Set `amount` to price a specific quantity (affects on-chain path selection for price impact). "
    "Use `ignore_pools` (comma-separated addresses) to exclude specific liquidity pools. "
    "Block and timestamp are mutually exclusive; omit both for latest block. "
    "Set `force=true` to bypass any cached error entry and attempt a fresh price lookup.",
)
async def price(
    token: str | None = Query(None, description="ERC-20 token address (0x...)"),
    block: str | None = Query(None, description="Block number (mutually exclusive with timestamp)"),
    amount: str | None = Query(None, description="Token amount to price (default: 1)"),
    ignore_pools: str | None = Query(None, description="Comma-separated pool addresses to exclude"),
    timestamp: str | None = Query(
        None, description="Unix epoch or ISO 8601 timestamp (mutually exclusive with block)"
    ),
    force: bool = Query(
        False,
        description="Bypass cached error entries and attempt a fresh price lookup (default: false)",
    ),
) -> Any:
    logger.debug("price_request", token=token, block=block, timestamp=timestamp, force=force)
    result = parse_price_params(token, block, amount, ignore_pools, timestamp)
    if isinstance(result, ParseError):
        price_requests_total.labels(chain=CHAIN_NAME, status="bad_request").inc()
        return _make_error_response(400, result.error)

    params = result.data
    actual_block = await _resolve_price_block(params)
    if isinstance(actual_block, JSONResponse):
        return actual_block

    logger.debug("price_resolved", token=params.token, block=actual_block)

    return await _handle_price_request(params, actual_block, force=force)


@app.get(
    "/prices",
    description="Batch-price multiple ERC-20 tokens in a single request. "
    "Returns a JSON array with one entry per token containing price (or null on failure), "
    "block, and block_timestamp. "
    "Partial failures return 200 with null prices for failed tokens. Max 100 tokens per call.",
)
async def prices(
    tokens: str | None = Query(
        None, description="Comma-separated ERC-20 token addresses (max 100)"
    ),
    block: str | None = Query(None, description="Block number (mutually exclusive with timestamp)"),
    amounts: str | None = Query(
        None,
        description="Comma-separated amounts, positionally matched to tokens; empty segments mean 'no amount'",
    ),
    timestamp: str | None = Query(
        None, description="Unix epoch or ISO 8601 timestamp (mutually exclusive with block)"
    ),
) -> Any:
    result = parse_batch_params(tokens, block, amounts, timestamp)
    if isinstance(result, ParseError):
        batch_requests_total.labels(chain=CHAIN_NAME, status="bad_request").inc()
        return _make_error_response(400, result.error)

    params = result.data

    # Determine the block to use
    block_result = await _resolve_batch_block(params)
    if isinstance(block_result, tuple):
        return block_result[1]
    actual_block = block_result

    start = time.monotonic()

    # Prepare results - check cache for each token
    results, tokens_to_fetch, indices_to_fetch = _prepare_batch_cache_check(params, actual_block)

    # Fetch prices for tokens not in cache
    if tokens_to_fetch:
        # Prepare amounts for the tokens we need to fetch (preserve positional correspondence)
        fetch_amounts: tuple[float | None, ...] | None = None
        if params.amounts is not None:
            fetch_amounts = tuple(params.amounts[i] for i in indices_to_fetch)

        try:
            prices = await asyncio.shield(
                _fetch_batch_prices(
                    tuple(tokens_to_fetch),
                    actual_block,
                    amounts=fetch_amounts,
                )
            )
        except TimeoutError:
            batch_requests_total.labels(chain=CHAIN_NAME, status="timeout").inc()
            return _make_timeout_response()

        # Fetch block timestamp once for all
        block_timestamp = await _fetch_block_timestamp(actual_block)

        # Fill in results
        _fill_batch_results(
            results,
            tokens_to_fetch,
            indices_to_fetch,
            prices,
            actual_block,
            block_timestamp,
            params,
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    batch_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
    batch_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)

    # Count success/failure
    success_count = sum(1 for r in results if r.get("price") is not None)
    logger.info(
        "batch_fetched",
        chain=CHAIN_NAME,
        total_tokens=len(params.tokens),
        success_count=success_count,
        block=actual_block,
        duration_ms=duration_ms,
    )

    return results


@app.get(
    "/check_bucket",
    description="Classify a token into its pricing bucket (e.g. 'atoken', 'curve lp', 'uni v2 lp'). "
    "Returns the bucket string or null if the token cannot be classified.",
)
async def check_bucket(
    token: str | None = Query(None, description="ERC-20 token address to classify"),
) -> Any:
    if not token:
        check_bucket_requests_total.labels(chain=CHAIN_NAME, status="bad_request").inc()
        return _make_error_response(400, "Missing required parameter: token")

    if not is_valid_address(token):
        check_bucket_requests_total.labels(chain=CHAIN_NAME, status="bad_request").inc()
        return _make_error_response(400, f"Invalid token address: {token}")

    start = time.monotonic()
    token_lock = await _get_token_lock(token)
    async with token_lock:
        try:
            from y import check_bucket as y_check_bucket

            bucket = await y_check_bucket(token, sync=False)
            duration_ms = int((time.monotonic() - start) * 1000)
            check_bucket_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
            check_bucket_request_duration_seconds.labels(chain=CHAIN_NAME).observe(
                duration_ms / 1000
            )

            # Fetch token metadata (symbol, name, decimals) alongside bucket.
            # ERC20 properties are memory-cached by ypricemagic after first call.
            metadata: dict[str, Any] = {}
            try:
                from y.classes.common import ERC20

                erc20 = ERC20(token, asynchronous=True)
                symbol, name, decimals = await asyncio.gather(
                    erc20.symbol,  # type: ignore[call-overload]
                    erc20.name,  # type: ignore[call-overload]
                    erc20.decimals,  # type: ignore[call-overload]
                )
                metadata = {"symbol": symbol, "name": name, "decimals": decimals}
            except Exception as meta_err:
                logger.warning(
                    "check_bucket_metadata_failed",
                    chain=CHAIN_NAME,
                    token=token,
                    error=str(meta_err),
                )

            logger.info(
                "check_bucket_success",
                chain=CHAIN_NAME,
                token=token,
                bucket=bucket,
                has_metadata=bool(metadata),
                duration_ms=duration_ms,
            )
            return {
                "token": token,
                "chain": CHAIN_NAME,
                "bucket": bucket,
                **metadata,
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            check_bucket_requests_total.labels(chain=CHAIN_NAME, status="error").inc()
            logger.error(
                "check_bucket_failed",
                chain=CHAIN_NAME,
                token=token if token else None,
                error=str(e),
                duration_ms=duration_ms,
            )
            return _make_error_response(
                500,
                f"Failed to classify token {token}: {e}",
            )
