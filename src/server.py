import asyncio
import math
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, make_asgi_app
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.cache import get_cached_price, set_cached_price
from src.logger import configure_logging, get_logger
from src.params import (
    ParseError,
    is_valid_address,
    parse_batch_params,
    parse_price_params,
    parse_quote_params,
)

if TYPE_CHECKING:
    from src.params import BatchParams

configure_logging()
logger = get_logger("server")

CHAIN_NAME = os.environ.get("CHAIN_NAME", "ethereum")

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
quote_requests_total = Counter(
    "quote_requests_total",
    "Total quote requests",
    ["chain", "status"],
)
quote_request_duration_seconds = Histogram(
    "quote_request_duration_seconds",
    "Quote request duration",
    ["chain"],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    logger.info("startup", chain=CHAIN_NAME)
    try:
        from brownie import network

        network_id = os.environ.get("BROWNIE_NETWORK_ID", f"{CHAIN_NAME}-custom")
        if not network.is_connected():  # type: ignore[attr-defined]
            network.connect(network_id)  # type: ignore[attr-defined]
        logger.info("brownie_connected", network_id=network_id)

        from dank_mids.helpers import setup_dank_w3_from_sync

        setup_dank_w3_from_sync(network.web3)
        logger.info("dank_mids_patched")

        from brownie import chain
        from y import get_price  # noqa: F401

        logger.info("chain_connected", chain=CHAIN_NAME, chain_id=chain.id, block=chain.height)
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise
    yield


app = FastAPI(title="ypricemagic API", lifespan=lifespan)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Mount static files at /static
# Note: StaticFiles bypasses middleware, so CORS headers won't be added
# This is fine for static assets (JS, CSS, JSON files)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Any:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
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
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
)
async def _fetch_price(
    token: str,
    block: int,
    amount: float | None = None,
    skip_cache: bool = False,
    ignore_pools: tuple[str, ...] = (),
    silent: bool = False,
) -> tuple[float, list[dict[str, Any]] | None] | None:
    """Fetch a single token price. Returns (price, trade_path) or None."""
    from y import get_price

    kwargs: dict[str, Any] = {
        "fail_to_None": True,
        "sync": False,
    }
    if amount is not None:
        kwargs["amount"] = amount
    if skip_cache:
        kwargs["skip_cache"] = True
    if ignore_pools:
        kwargs["ignore_pools"] = ignore_pools
    if silent:
        kwargs["silent"] = True

    p = await get_price(token, block, **kwargs)
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
    skip_cache: bool = False,
    silent: bool = False,
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
    if skip_cache:
        kwargs["skip_cache"] = True
    if silent:
        kwargs["silent"] = True

    try:
        results = await get_prices(tokens, block, **kwargs)
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
    """Create a JSON error response."""
    return JSONResponse(status_code=status, content={"error": message})


def _handle_price_error(e: Exception, token: str, block: int, duration_ms: int) -> JSONResponse:
    """Handle exceptions from price fetching and return appropriate response."""
    inner = e.__cause__ if isinstance(e, RetryError) else e
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
    return _make_error_response(
        500,
        f"Price lookup failed for {token} at block {block}: {msg}",
    )


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

        # Check cache only if: no amount AND not skip_cache
        if token_amount is None and not params.skip_cache:
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


@app.get("/price")
async def price(
    token: str | None = Query(None),
    block: str | None = Query(None),
    amount: str | None = Query(None),
    skip_cache: str | None = Query(None),
    ignore_pools: str | None = Query(None),
    silent: str | None = Query(None),
    timestamp: str | None = Query(None),
) -> Any:
    result = parse_price_params(token, block, amount, skip_cache, ignore_pools, silent, timestamp)
    if isinstance(result, ParseError):
        price_requests_total.labels(chain=CHAIN_NAME, status="bad_request").inc()
        return _make_error_response(400, result.error)

    params = result.data

    from brownie import chain as brownie_chain

    # Determine the block to use
    if params.timestamp is not None:
        try:
            actual_block = await _resolve_block_from_timestamp(params.timestamp)
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
    else:
        actual_block = params.block if params.block is not None else brownie_chain.height

    # Check cache only if: no amount AND not skip_cache
    if params.amount is None and not params.skip_cache:
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
            return {
                "chain": CHAIN_NAME,
                "token": params.token,
                "block": actual_block,
                "price": cached["price"],
                "cached": True,
                "block_timestamp": cached.get("block_timestamp"),
            }

    start = time.monotonic()
    try:
        fetch_result = await _fetch_price(
            params.token,
            actual_block,
            amount=params.amount,
            skip_cache=params.skip_cache,
            ignore_pools=params.ignore_pools,
            silent=params.silent,
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _handle_price_error(e, params.token, actual_block, duration_ms)

    # Handle None return from get_price with fail_to_None=True
    if fetch_result is None:
        price_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        logger.warning("price_not_found", token=params.token[:10], block=actual_block)
        return _make_error_response(
            404,
            f"No price found for {params.token} at block {actual_block} on {CHAIN_NAME}",
        )

    price_float, trade_path = fetch_result
    duration_ms = int((time.monotonic() - start) * 1000)

    # Fetch block timestamp
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

    response: dict[str, Any] = {
        "chain": CHAIN_NAME,
        "token": params.token,
        "block": actual_block,
        "price": price_float,
        "cached": False,
        "block_timestamp": block_timestamp,
        "trade_path": trade_path,
    }
    if params.amount is not None:
        response["amount"] = params.amount
    return response


@app.get("/prices")
async def prices(
    tokens: str | None = Query(None),
    block: str | None = Query(None),
    amounts: str | None = Query(None),
    timestamp: str | None = Query(None),
    skip_cache: str | None = Query(None),
    silent: str | None = Query(None),
) -> Any:
    """Batch pricing endpoint.

    Returns a JSON array of results. Each element has:
    - token: the token address
    - block: the block number used
    - price: float or null (if price unavailable)
    - block_timestamp: Unix epoch or null
    - cached: boolean (true if from cache)

    Partial failures return 200 with null prices for failed tokens.
    All-failures also return 200.
    """
    result = parse_batch_params(tokens, block, amounts, timestamp, skip_cache, silent)
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

        prices = await _fetch_batch_prices(
            tuple(tokens_to_fetch),
            actual_block,
            amounts=fetch_amounts,
            skip_cache=params.skip_cache,
            silent=params.silent,
        )

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


@app.get("/check_bucket")
async def check_bucket(
    token: str | None = Query(None),
) -> Any:
    """Token classification endpoint.

    Returns the pricing bucket classification for a token.

    Response:
    - token: the token address
    - chain: the chain name
    - bucket: classification string (e.g., "atoken", "curve lp") or null if unclassifiable
    """
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


@app.get("/quote")
async def quote(
    from_token: str | None = Query(None, alias="from"),
    to_token: str | None = Query(None, alias="to"),
    amount: str | None = Query(None),
    block: str | None = Query(None),
    timestamp: str | None = Query(None),
) -> Any:
    """From→to token quote endpoint.

    Computes output_amount = amount * (price_from / price_to).

    Response:
    - from: source token address
    - to: destination token address
    - amount: input amount
    - output_amount: computed output amount
    - block: block number used
    - chain: chain name
    - block_timestamp: Unix epoch for the block
    - route: "divide" for USD price division, "identity" for same-token quotes

    Returns 400 for invalid params.
    Returns 404 if either token cannot be priced.
    """
    result = parse_quote_params(from_token, to_token, amount, block, timestamp)
    if isinstance(result, ParseError):
        quote_requests_total.labels(chain=CHAIN_NAME, status="bad_request").inc()
        return _make_error_response(400, result.error)

    params = result.data

    from brownie import chain as brownie_chain

    # Determine the block to use
    if params.timestamp is not None:
        try:
            actual_block = await _resolve_block_from_timestamp(params.timestamp)
        except Exception as e:
            logger.error(
                "quote_timestamp_resolution_failed",
                timestamp=params.timestamp,
                error=str(e),
            )
            return _make_error_response(
                502,
                f"Failed to resolve timestamp {params.timestamp} to block: {e}",
            )
    else:
        actual_block = params.block if params.block is not None else brownie_chain.height

    start = time.monotonic()

    # Same-token quote: output_amount == amount, route = "identity"
    if params.from_token.lower() == params.to_token.lower():
        block_timestamp = await _fetch_block_timestamp(actual_block)
        duration_ms = int((time.monotonic() - start) * 1000)
        quote_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
        quote_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)
        logger.info(
            "quote_identity",
            chain=CHAIN_NAME,
            from_token=params.from_token[:10],
            to_token=params.to_token[:10],
            amount=params.amount,
            block=actual_block,
            duration_ms=duration_ms,
        )
        return {
            "from": params.from_token,
            "to": params.to_token,
            "amount": params.amount,
            "output_amount": params.amount,
            "block": actual_block,
            "chain": CHAIN_NAME,
            "block_timestamp": block_timestamp,
            "route": "identity",
        }

    # Fetch USD price for from_token
    try:
        from_price = await _fetch_price(params.from_token, actual_block)
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _handle_price_error(e, params.from_token, actual_block, duration_ms)

    if from_price is None:
        quote_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        logger.warning(
            "quote_from_token_not_found",
            from_token=params.from_token[:10],
            block=actual_block,
        )
        return _make_error_response(
            404,
            f"No price found for from token {params.from_token} at block {actual_block} on {CHAIN_NAME}",
        )

    # Fetch USD price for to_token
    try:
        to_price = await _fetch_price(params.to_token, actual_block)
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _handle_price_error(e, params.to_token, actual_block, duration_ms)

    if to_price is None:
        quote_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        logger.warning(
            "quote_to_token_not_found",
            to_token=params.to_token[:10],
            block=actual_block,
        )
        return _make_error_response(
            404,
            f"No price found for to token {params.to_token} at block {actual_block} on {CHAIN_NAME}",
        )

    # Guard against ZeroDivisionError: to_price == 0.0 means unpriceable destination
    if to_price == 0.0:
        quote_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        logger.warning(
            "quote_to_token_zero_price",
            to_token=params.to_token[:10],
            block=actual_block,
        )
        return _make_error_response(
            404,
            f"Cannot price destination token {params.to_token} at block {actual_block} on {CHAIN_NAME}",
        )

    # Compute output_amount using divide strategy
    output_amount = params.amount * (from_price / to_price)

    # Fetch block timestamp
    block_timestamp = await _fetch_block_timestamp(actual_block)

    duration_ms = int((time.monotonic() - start) * 1000)
    quote_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
    quote_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)
    logger.info(
        "quote_success",
        chain=CHAIN_NAME,
        from_token=params.from_token[:10],
        to_token=params.to_token[:10],
        amount=params.amount,
        output_amount=output_amount,
        from_price=from_price,
        to_price=to_price,
        block=actual_block,
        duration_ms=duration_ms,
    )

    return {
        "from": params.from_token,
        "to": params.to_token,
        "amount": params.amount,
        "output_amount": output_amount,
        "block": actual_block,
        "chain": CHAIN_NAME,
        "block_timestamp": block_timestamp,
        "route": "divide",
    }


@app.get("/")
async def index() -> FileResponse:
    """Serve the main UI from static files."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    return FileResponse(index_path, media_type="text/html")
