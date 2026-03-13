import asyncio
import logging
import math
import os
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

from src.cache import close_cache, get_cached_price, set_cached_price
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

PRICE_TIMEOUT = 30.0

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    # Install after uvicorn has configured its loggers (CLI resets them at startup).
    logging.getLogger("uvicorn.access").addFilter(_HealthAccessFilter())

    logger.info("startup", chain=CHAIN_NAME)
    try:
        from brownie import network

        network_id = os.environ.get("BROWNIE_NETWORK_ID", f"{CHAIN_NAME}-custom")
        if not network.is_connected():  # type: ignore[attr-defined]
            network.connect(network_id)  # type: ignore[attr-defined]
        logger.info("brownie_connected", network_id=network_id)

        # Workaround: dank_mids sets concurrent.futures.process.EXTRA_QUEUED_CALLS
        # to 50,000 at import time. On macOS, SEM_VALUE_MAX is 32,767, so any
        # ProcessPoolExecutor queue exceeding that limit fails with EINVAL.
        # Pre-import dank_mids (triggers the monkey-patch), then cap the value.
        import sys

        if sys.platform == "darwin":
            import concurrent.futures.process as _cfp

            import dank_mids  # noqa: F401 — triggers EXTRA_QUEUED_CALLS = 50000

            _sem_value_max: int = getattr(
                __import__("multiprocessing.synchronize", fromlist=["SEM_VALUE_MAX"]),
                "SEM_VALUE_MAX",
                32767,
            )
            _cfp.EXTRA_QUEUED_CALLS = min(  # type: ignore[misc]
                _cfp.EXTRA_QUEUED_CALLS, _sem_value_max - 1
            )

        from dank_mids.helpers import setup_dank_w3_from_sync

        setup_dank_w3_from_sync(network.web3)
        logger.info("dank_mids_patched")

        from brownie import chain
        from y import get_price  # noqa: F401

        logger.info("chain_connected", chain=CHAIN_NAME, chain_id=chain.id, block=chain.height)
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

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
    description="ERC-20 token pricing API. Returns USD prices (or token-to-token quotes) at any historical block or timestamp. Supports single and batch lookups.",
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
            "source": step.source,
            "input_token": step.input_token,
            "output_token": step.output_token,
            "pool": step.pool,
            "price": step.price,
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

    p = await asyncio.wait_for(get_price(token, block, **kwargs), timeout=PRICE_TIMEOUT)
    if p is None:
        return None
    price_float = float(p)
    if math.isnan(price_float) or math.isinf(price_float):
        raise ValueError(f"Invalid price value {p} for {token} at block {block}")
    if price_float < 0:
        raise ValueError(f"Negative price {price_float} for {token} at block {block}")
    trade_path = _serialize_trade_path(p)
    return price_float, trade_path


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
                        token=tokens[i][:10],
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
        token=token[:10],
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
        return params.block if params.block is not None else brownie_chain.height

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


def _make_identity_quote_response(
    token: str,
    quote_to: str,
    amount: float,
    block: int,
    block_timestamp: int | None,
) -> dict[str, Any]:
    return {
        "from": token,
        "to": quote_to,
        "amount": amount,
        "output_amount": amount,
        "block": block,
        "chain": CHAIN_NAME,
        "block_timestamp": block_timestamp,
        "route": "identity",
        "from_price": None,
        "to_price": None,
        "from_trade_path": None,
        "to_trade_path": None,
    }


def _make_quote_not_found_response(direction: str, token: str, block: int) -> JSONResponse:
    return _make_error_response(
        404,
        f"No price found for {direction} token {token} at block {block} on {CHAIN_NAME}",
    )


async def _handle_quote_mode(
    params: Any, actual_block: int, quote_to: str, quote_amount: float
) -> Any:
    start = time.monotonic()

    if params.token.lower() == quote_to.lower():
        block_timestamp = await _fetch_block_timestamp(actual_block)
        duration_ms = int((time.monotonic() - start) * 1000)
        price_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
        price_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)
        return _make_identity_quote_response(
            params.token, quote_to, quote_amount, actual_block, block_timestamp
        )

    try:
        from_result = await _fetch_price(
            params.token,
            actual_block,
            amount=params.amount,
            ignore_pools=params.ignore_pools,
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _handle_price_error(e, params.token, actual_block, duration_ms)

    if from_result is None:
        price_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        return _make_quote_not_found_response("from", params.token, actual_block)

    from_price, from_trade_path = from_result

    try:
        to_result = await _fetch_price(quote_to, actual_block)
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _handle_price_error(e, quote_to, actual_block, duration_ms)

    if to_result is None:
        price_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        return _make_quote_not_found_response("to", quote_to, actual_block)

    to_price, to_trade_path = to_result
    if to_price == 0.0:
        price_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        return _make_error_response(
            404,
            f"Cannot price destination token {quote_to} at block {actual_block} on {CHAIN_NAME}",
        )

    output_amount = quote_amount * (from_price / to_price)
    block_timestamp = await _fetch_block_timestamp(actual_block)
    duration_ms = int((time.monotonic() - start) * 1000)
    price_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
    price_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)
    return {
        "from": params.token,
        "to": quote_to,
        "amount": quote_amount,
        "output_amount": output_amount,
        "block": actual_block,
        "chain": CHAIN_NAME,
        "block_timestamp": block_timestamp,
        "route": "divide",
        "from_price": from_price,
        "to_price": to_price,
        "from_trade_path": from_trade_path,
        "to_trade_path": to_trade_path,
    }


async def _handle_usd_mode(params: Any, actual_block: int, quote_amount: float) -> Any:
    if params.amount is None:
        cached = get_cached_price(params.token, actual_block)
        if cached is not None:
            logger.info(
                "cache_hit",
                chain=CHAIN_NAME,
                token=params.token[:10],
                block=actual_block,
                price=cached["price"],
            )
            price_requests_total.labels(chain=CHAIN_NAME, status="cache_hit").inc()
            cached_price = float(cached["price"])  # type: ignore[arg-type]
            return {
                "from": params.token,
                "to": "USD",
                "amount": quote_amount,
                "output_amount": cached_price * quote_amount,
                "block": actual_block,
                "chain": CHAIN_NAME,
                "block_timestamp": cached.get("block_timestamp"),
                "route": "usd",
                "from_price": cached_price,
                "to_price": 1.0,
                "from_trade_path": None,
                "to_trade_path": None,
            }

    start = time.monotonic()
    try:
        fetch_result = await _fetch_price(
            params.token,
            actual_block,
            amount=params.amount,
            ignore_pools=params.ignore_pools,
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _handle_price_error(e, params.token, actual_block, duration_ms)

    if fetch_result is None:
        price_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        logger.warning("price_not_found", token=params.token[:10], block=actual_block)
        return _make_error_response(
            404,
            f"No price found for {params.token} at block {actual_block} on {CHAIN_NAME}",
        )

    price_float, trade_path = fetch_result
    duration_ms = int((time.monotonic() - start) * 1000)
    block_timestamp = await _fetch_block_timestamp(actual_block)

    if params.amount is None:
        set_cached_price(params.token, actual_block, price_float, block_timestamp=block_timestamp)
    price_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
    price_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)
    logger.info(
        "price_fetched",
        chain=CHAIN_NAME,
        token=params.token[:10],
        block=actual_block,
        price=price_float,
        amount=params.amount,
        duration_ms=duration_ms,
    )

    return {
        "from": params.token,
        "to": "USD",
        "amount": quote_amount,
        "output_amount": price_float * quote_amount,
        "block": actual_block,
        "chain": CHAIN_NAME,
        "block_timestamp": block_timestamp,
        "route": "usd",
        "from_price": price_float,
        "to_price": 1.0,
        "from_trade_path": trade_path,
        "to_trade_path": None,
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
    "Pass `to` as another token address to get a token-to-token quote instead. "
    "Set `amount` to price a specific quantity (default 1). "
    "Use `ignore_pools` (comma-separated addresses) to exclude specific liquidity pools. "
    "Block and timestamp are mutually exclusive; omit both for latest block.",
)
async def price(
    token: str | None = Query(None, description="ERC-20 token address (0x...)"),
    to: str | None = Query(
        None, description="Quote currency: 'USD' (default) or another token address"
    ),
    block: str | None = Query(None, description="Block number (mutually exclusive with timestamp)"),
    amount: str | None = Query(None, description="Token amount to price (default: 1)"),
    ignore_pools: str | None = Query(None, description="Comma-separated pool addresses to exclude"),
    timestamp: str | None = Query(
        None, description="Unix epoch or ISO 8601 timestamp (mutually exclusive with block)"
    ),
) -> Any:
    result = parse_price_params(token, to, block, amount, ignore_pools, timestamp)
    if isinstance(result, ParseError):
        price_requests_total.labels(chain=CHAIN_NAME, status="bad_request").inc()
        return _make_error_response(400, result.error)

    params = result.data
    quote_to = params.to
    quote_amount = params.amount if params.amount is not None else 1.0
    actual_block = await _resolve_price_block(params)
    if isinstance(actual_block, JSONResponse):
        return actual_block

    if quote_to == "USD":
        return await _handle_usd_mode(params, actual_block, quote_amount)

    return await _handle_quote_mode(params, actual_block, quote_to, quote_amount)


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
            prices = await _fetch_batch_prices(
                tuple(tokens_to_fetch),
                actual_block,
                amounts=fetch_amounts,
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
    try:
        from y import check_bucket as y_check_bucket

        bucket = await y_check_bucket(token, sync=False)
        duration_ms = int((time.monotonic() - start) * 1000)
        check_bucket_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
        check_bucket_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)
        logger.info(
            "check_bucket_success",
            chain=CHAIN_NAME,
            token=token[:10],
            bucket=bucket,
            duration_ms=duration_ms,
        )
        return {
            "token": token,
            "chain": CHAIN_NAME,
            "bucket": bucket,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        check_bucket_requests_total.labels(chain=CHAIN_NAME, status="error").inc()
        logger.error(
            "check_bucket_failed",
            chain=CHAIN_NAME,
            token=token[:10] if token else None,
            error=str(e),
            duration_ms=duration_ms,
        )
        return _make_error_response(
            500,
            f"Failed to classify token {token}: {e}",
        )
