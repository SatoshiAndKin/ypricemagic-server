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
from fastapi.responses import HTMLResponse, JSONResponse
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
from src.params import ParseError, is_valid_address, parse_batch_params, parse_price_params

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
) -> float | None:
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
    return price_float


async def _fetch_batch_prices(
    tokens: tuple[str, ...],
    block: int,
    amounts: tuple[float | None, ...] | None = None,
    skip_cache: bool = False,
    silent: bool = False,
) -> list[float | None]:
    """Fetch prices for multiple tokens in parallel.

    Returns a list of prices (float) or None for tokens that couldn't be priced.
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
        # results should be a list parallel to tokens
        prices: list[float | None] = []
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
                    prices.append(price_float)
        return prices
    except Exception as e:
        logger.error("batch_fetch_failed", block=block, error=str(e))
        # Return None for all tokens on complete failure
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
    prices: list[float | None],
    block: int,
    block_timestamp: int | None,
    params: "BatchParams",
) -> None:
    """Fill in batch results with fetched prices and cache them."""
    for idx, token in enumerate(tokens_to_fetch):
        i = indices_to_fetch[idx]
        price_val = prices[idx]
        token_amount = params.amounts[i] if params.amounts is not None else None

        results[i] = {
            "token": token,
            "block": block,
            "price": price_val,
            "block_timestamp": block_timestamp,
            "cached": False,
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
        price_float = await _fetch_price(
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
    if price_float is None:
        price_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
        logger.warning("price_not_found", token=params.token[:10], block=actual_block)
        return _make_error_response(
            404,
            f"No price found for {params.token} at block {actual_block} on {CHAIN_NAME}",
        )

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


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ypricemagic API</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
    h1 { margin-bottom: 20px; color: #333; }
    h2 { margin: 30px 0 15px; color: #444; font-size: 20px; border-bottom: 2px solid #ddd; padding-bottom: 8px; }
    form { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .form-group { margin-bottom: 16px; }
    .form-row { display: flex; gap: 16px; }
    .form-row .form-group { flex: 1; }
    label { display: block; font-weight: 600; margin-bottom: 6px; color: #555; }
    input, select, textarea { width: 100%; padding: 10px; font-size: 14px; border: 1px solid #ddd; border-radius: 4px; }
    input, textarea { font-family: monospace; }
    input:focus, select:focus, textarea:focus { outline: none; border-color: #0066cc; }
    input:disabled { background: #f0f0f0; color: #999; }
    textarea { min-height: 80px; resize: vertical; }
    .checkbox-group { display: flex; align-items: center; gap: 8px; }
    .checkbox-group input { width: auto; }
    .checkbox-group label { margin-bottom: 0; font-weight: normal; }
    button { padding: 12px 24px; font-size: 16px; cursor: pointer; background: #0066cc; color: white; border: none; border-radius: 4px; min-width: 160px; text-align: center; }
    button:hover { background: #0052a3; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .result { background: #1e1e1e; color: #d4d4d4; padding: 20px; border-radius: 8px; display: none; margin-top: 20px; }
    .result.show { display: block; }
    .error { color: #e74c3c; }
    .result-header { color: #888; margin-bottom: 12px; font-size: 14px; }
    .field { margin-bottom: 12px; }
    .field-label { color: #888; font-size: 12px; text-transform: uppercase; }
    .field-value { color: #4ec9b0; word-break: break-all; }
    .field-value.number { color: #b5cea8; font-size: 24px; }
    .field-value .dim { color: #888; font-size: 11px; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
    th { color: #888; font-size: 12px; text-transform: uppercase; }
    td { color: #d4d4d4; font-family: monospace; font-size: 13px; }
    td.null { color: #666; font-style: italic; }
    .hint { font-size: 12px; color: #888; margin-top: 4px; }
    .token-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
    .token-row input.token-addr { flex: 3; }
    .token-row input.token-amt { flex: 1; min-width: 100px; }
    .token-row .btn-remove { background: #e74c3c; color: white; border: none; border-radius: 4px; padding: 10px 12px; cursor: pointer; font-size: 14px; line-height: 1; flex-shrink: 0; }
    .token-row .btn-remove:hover { background: #c0392b; }
    .btn-add { background: #27ae60; color: white; border: none; border-radius: 4px; padding: 12px 24px; cursor: pointer; font-size: 16px; margin-top: 4px; min-width: 160px; text-align: center; }
    .btn-add:hover { background: #219a52; }
  </style>
</head>
<body>
  <h1>ypricemagic Price Lookup</h1>

  <!-- Global Chain Selector -->
  <div class="form-group">
    <label for="chain">Chain (applies to all forms)</label>
    <select id="chain">
      <option value="ethereum">Ethereum</option>
      <option value="arbitrum">Arbitrum</option>
      <option value="optimism">Optimism</option>
      <option value="base">Base</option>
    </select>
  </div>

  <!-- Single Price Form -->
  <h2>Single Token Price</h2>
  <form id="price-form">
    <div class="form-group">
      <label for="price-token">Token Address</label>
      <input type="text" id="price-token" placeholder="0x..." value="0x6B175474E89094C44Da98b954EedeAC495271d0F">
    </div>
    <div class="form-group">
      <label for="price-block">Block / Date (optional)</label>
      <input type="text" id="price-block" placeholder="defaults to latest">
      <div class="hint" id="price-block-hint">Block number, or type "/" for a date picker. Defaults to latest block.</div>
    </div>
    <div class="form-group">
      <label for="price-amount">Amount (optional, token units for price impact)</label>
      <input type="text" id="price-amount" placeholder="e.g. 1">
    </div>

    <div class="form-group">
      <label for="price-ignore-pools">Ignore Pools (optional, comma-separated addresses)</label>
      <input type="text" id="price-ignore-pools" placeholder="0xabc...,0xdef...">
    </div>
    <button type="submit" id="price-submit">Get Price</button>
  </form>
  <div id="price-result" class="result"></div>

  <!-- Batch Pricing Form -->
  <h2>Batch Token Pricing</h2>
  <form id="batch-form">
    <div class="form-group">
      <label>Tokens</label>
      <div id="batch-token-rows"></div>
      <button type="button" id="batch-add-token" class="btn-add">+ Add Token</button>
    </div>
    <div class="form-group">
      <label for="batch-block">Block / Date (optional)</label>
      <input type="text" id="batch-block" placeholder="defaults to latest">
      <div class="hint" id="batch-block-hint">Block number, or type "/" for a date picker. Defaults to latest block.</div>
    </div>

    <button type="submit" id="batch-submit">Get Prices</button>
  </form>
  <div id="batch-result" class="result"></div>

  <!-- Token Classification Form -->
  <h2>Token Classification</h2>
  <form id="bucket-form">
    <div class="form-group">
      <label for="bucket-token">Token Address</label>
      <input type="text" id="bucket-token" placeholder="0x...">
    </div>
    <button type="submit" id="bucket-submit">Check Bucket</button>
  </form>
  <div id="bucket-result" class="result"></div>

  <script>
    // Utility functions
    function getChain() {
      return document.getElementById('chain').value;
    }

    function escapeHtml(str) {
      if (str == null) return '';
      return String(str).replace(/[&<>"']/g, function(c) {
        return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[c];
      });
    }

    function showError(resultEl, msg) {
      resultEl.className = 'result show';
      resultEl.innerHTML = '<div class="error">' + escapeHtml(msg) + '</div>';
    }

    function showLoading(resultEl, msg) {
      resultEl.className = 'result show';
      resultEl.innerHTML = '<div class="result-header">' + escapeHtml(msg) + '</div>';
    }

    // Switch block field to date picker when "/" is typed
    function setupDatePickerSwitch(blockId, hintId) {
      const input = document.getElementById(blockId);
      const hint = document.getElementById(hintId);

      function switchToDatePicker() {
        input.type = 'datetime-local';
        input.value = '';
        hint.innerHTML = 'Pick a date/time. <a href="#" style="color:#58a6ff;cursor:pointer;" id="' + blockId + '-clear">Clear</a> to switch back to block number.';
        document.getElementById(blockId + '-clear').addEventListener('click', function(e) {
          e.preventDefault();
          switchToBlock();
        });
      }

      function switchToBlock() {
        input.type = 'text';
        input.value = '';
        input.placeholder = 'defaults to latest';
        hint.textContent = 'Block number, or type "/" for a date picker. Defaults to latest block.';
      }

      input.addEventListener('input', function() {
        if (this.type === 'text' && this.value.includes('/')) {
          switchToDatePicker();
        }
      });

      input.addEventListener('change', function() {
        if (this.type === 'datetime-local' && !this.value) {
          switchToBlock();
        }
      });
    }

    setupDatePickerSwitch('price-block', 'price-block-hint');
    setupDatePickerSwitch('batch-block', 'batch-block-hint');

    // Single Price Form
    const priceForm = document.getElementById('price-form');
    const priceResult = document.getElementById('price-result');
    const priceSubmit = document.getElementById('price-submit');

    function chainMismatchWarning(expected, actual) {
      if (actual && actual !== expected) {
        return `<div class="field" style="background:#553300;padding:8px;border-radius:4px;margin-bottom:12px;">
          <div class="field-label" style="color:#ffaa00;">&#9888; Chain Mismatch</div>
          <div class="field-value" style="color:#ffcc44;">Expected <b>${escapeHtml(expected)}</b> but backend reported <b>${escapeHtml(actual)}</b>. Check your nginx routing.</div>
        </div>`;
      }
      return '';
    }

    function showPriceResult(data, chain) {
      priceResult.className = 'result show';
      const mismatch = chainMismatchWarning(chain, data.chain);
      const timestampField = data.block_timestamp != null ? `
        <div class="field">
          <div class="field-label">Block Timestamp</div>
          <div class="field-value">${escapeHtml(data.block_timestamp)}</div>
        </div>` : '';
      const amountField = data.amount != null ? `
        <div class="field">
          <div class="field-label">Amount</div>
          <div class="field-value">${escapeHtml(data.amount)}</div>
        </div>` : '';
      priceResult.innerHTML = `
        <div class="result-header">Price Result</div>${mismatch}
        <div class="field">
          <div class="field-label">Chain</div>
          <div class="field-value">${escapeHtml(data.chain)}</div>
        </div>
        <div class="field">
          <div class="field-label">Token</div>
          <div class="field-value"><span class="dim">${escapeHtml(data.token)}</span></div>
        </div>
        <div class="field">
          <div class="field-label">Block</div>
          <div class="field-value">${escapeHtml(data.block)}</div>
        </div>${timestampField}${amountField}
        <div class="field">
          <div class="field-label">Price (USD per token)</div>
          <div class="field-value number">${escapeHtml(data.price)}</div>
        </div>
        <div class="field">
          <div class="field-label">Cached</div>
          <div class="field-value">${data.cached ? 'yes' : 'no'}</div>
        </div>
      `;
    }

    priceForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const chain = getChain();
      const token = document.getElementById('price-token').value.trim();
      const blockInput = document.getElementById('price-block');
      const blockVal = blockInput.value.trim();
      const isDate = blockInput.type === 'datetime-local';
      const amount = document.getElementById('price-amount').value.trim();
      const ignorePools = document.getElementById('price-ignore-pools').value.trim();

      priceSubmit.disabled = true;
      priceSubmit.textContent = 'Fetching...';
      showLoading(priceResult, 'Fetching price...');

      try {
        const params = new URLSearchParams({ token });
        if (blockVal && isDate) {
          params.set('timestamp', new Date(blockVal).toISOString());
        } else if (blockVal) {
          params.set('block', blockVal);
        }
        if (amount) params.set('amount', amount);
        if (ignorePools) params.set('ignore_pools', ignorePools);

        const res = await fetch('/' + chain + '/price?' + params.toString());
        const data = await res.json();

        if (data.error) {
          showError(priceResult, data.error);
        } else {
          showPriceResult(data, chain);
        }
      } catch (err) {
        showError(priceResult, 'Request failed: ' + err.message);
      } finally {
        priceSubmit.disabled = false;
        priceSubmit.textContent = 'Get Price';
      }
    });

    // Batch Pricing Form — dynamic token rows
    const batchForm = document.getElementById('batch-form');
    const batchResult = document.getElementById('batch-result');
    const batchSubmit = document.getElementById('batch-submit');
    const batchTokenRows = document.getElementById('batch-token-rows');

    function addTokenRow(token, amount) {
      const row = document.createElement('div');
      row.className = 'token-row';
      row.innerHTML = `<input type="text" class="token-addr" placeholder="0x..." value="${escapeHtml(token || '')}">` +
        `<input type="text" class="token-amt" placeholder="Amount (opt)" value="${escapeHtml(amount || '')}">` +
        `<button type="button" class="btn-remove" title="Remove">&times;</button>`;
      row.querySelector('.btn-remove').addEventListener('click', function() {
        row.remove();
      });
      batchTokenRows.appendChild(row);
    }

    document.getElementById('batch-add-token').addEventListener('click', function() {
      addTokenRow('', '');
    });

    // Start with one empty row
    addTokenRow('', '');

    function showBatchResult(data) {
      batchResult.className = 'result show';
      if (!Array.isArray(data)) {
        showError(batchResult, data.error || 'Unexpected response format');
        return;
      }

      let rows = '';
      for (const item of data) {
        const priceDisplay = item.price !== null ? escapeHtml(item.price) : '<span class="null">null</span>';
        const cachedDisplay = item.cached ? 'yes' : 'no';
        const tsDisplay = item.block_timestamp !== null ? escapeHtml(item.block_timestamp) : '-';
        rows += `<tr>
          <td>${escapeHtml(item.token)}</td>
          <td>${escapeHtml(item.block)}</td>
          <td>${priceDisplay}</td>
          <td>${tsDisplay}</td>
          <td>${cachedDisplay}</td>
        </tr>`;
      }

      batchResult.innerHTML = `
        <div class="result-header">Batch Results (${escapeHtml(data.length)} tokens)</div>
        <table>
          <thead>
            <tr>
              <th>Token</th>
              <th>Block</th>
              <th>Price</th>
              <th>Timestamp</th>
              <th>Cached</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    batchForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const chain = getChain();

      const rows = batchTokenRows.querySelectorAll('.token-row');
      const tokenList = [];
      const amountList = [];
      let hasAnyAmount = false;
      for (const row of rows) {
        const t = row.querySelector('.token-addr').value.trim();
        const a = row.querySelector('.token-amt').value.trim();
        if (t) {
          tokenList.push(t);
          amountList.push(a);
          if (a) hasAnyAmount = true;
        }
      }
      const tokens = tokenList.join(',');
      const amounts = hasAnyAmount ? amountList.join(',') : '';

      const batchBlockInput = document.getElementById('batch-block');
      const batchBlockVal = batchBlockInput.value.trim();
      const batchIsDate = batchBlockInput.type === 'datetime-local';
      if (!tokens) {
        showError(batchResult, 'Add at least one token address');
        return;
      }

      batchSubmit.disabled = true;
      batchSubmit.textContent = 'Fetching...';
      showLoading(batchResult, 'Fetching batch prices...');

      try {
        const params = new URLSearchParams({ tokens });
        if (batchBlockVal && batchIsDate) {
          params.set('timestamp', new Date(batchBlockVal).toISOString());
        } else if (batchBlockVal) {
          params.set('block', batchBlockVal);
        }
        if (amounts) params.set('amounts', amounts);

        const res = await fetch('/' + chain + '/prices?' + params.toString());
        const data = await res.json();

        if (data.error) {
          showError(batchResult, data.error);
        } else {
          showBatchResult(data);
        }
      } catch (err) {
        showError(batchResult, 'Request failed: ' + err.message);
      } finally {
        batchSubmit.disabled = false;
        batchSubmit.textContent = 'Get Prices';
      }
    });

    // Token Classification Form
    const bucketForm = document.getElementById('bucket-form');
    const bucketResult = document.getElementById('bucket-result');
    const bucketSubmit = document.getElementById('bucket-submit');

    function showBucketResult(data, chain) {
      bucketResult.className = 'result show';
      const mismatch = chainMismatchWarning(chain, data.chain);
      const bucketDisplay = data.bucket !== null ? escapeHtml(data.bucket) : '<span class="null">null</span>';
      bucketResult.innerHTML = `
        <div class="result-header">Classification Result</div>${mismatch}
        <div class="field">
          <div class="field-label">Token</div>
          <div class="field-value"><span class="dim">${escapeHtml(data.token)}</span></div>
        </div>
        <div class="field">
          <div class="field-label">Chain</div>
          <div class="field-value">${escapeHtml(data.chain)}</div>
        </div>
        <div class="field">
          <div class="field-label">Bucket</div>
          <div class="field-value">${bucketDisplay}</div>
        </div>
      `;
    }

    bucketForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const chain = getChain();
      const token = document.getElementById('bucket-token').value.trim();

      if (!token) {
        showError(bucketResult, 'Token address is required');
        return;
      }

      bucketSubmit.disabled = true;
      bucketSubmit.textContent = 'Checking...';
      showLoading(bucketResult, 'Classifying token (this may take 10-30s)...');

      try {
        const res = await fetch('/' + chain + '/check_bucket?token=' + encodeURIComponent(token));
        const data = await res.json();

        if (data.error) {
          showError(bucketResult, data.error);
        } else {
          showBucketResult(data, chain);
        }
      } catch (err) {
        showError(bucketResult, 'Request failed: ' + err.message);
      } finally {
        bucketSubmit.disabled = false;
        bucketSubmit.textContent = 'Check Bucket';
      }
    });

    // Load URL params to restore form state
    const params = new URLSearchParams(window.location.search);
    if (params.get('chain')) document.getElementById('chain').value = params.get('chain');
    if (params.get('token')) document.getElementById('price-token').value = params.get('token');
    if (params.get('block')) document.getElementById('price-block').value = params.get('block');
    if (params.get('timestamp')) {
      const priceBlockEl = document.getElementById('price-block');
      priceBlockEl.type = 'datetime-local';
      const d = new Date(params.get('timestamp'));
      if (!isNaN(d)) priceBlockEl.value = d.toISOString().slice(0, 16);
      const priceHint = document.getElementById('price-block-hint');
      priceHint.innerHTML = 'Pick a date/time. <a href="#" style="color:#58a6ff;cursor:pointer;" id="price-block-clear-restore">Clear</a> to switch back to block number.';
      document.getElementById('price-block-clear-restore').addEventListener('click', function(e) {
        e.preventDefault();
        priceBlockEl.type = 'text';
        priceBlockEl.value = '';
        priceBlockEl.placeholder = 'defaults to latest';
        priceHint.textContent = 'Block number, or type "/" for a date picker. Defaults to latest block.';
      });
    }
    if (params.get('amount')) document.getElementById('price-amount').value = params.get('amount');
    if (params.get('ignore_pools')) document.getElementById('price-ignore-pools').value = params.get('ignore_pools');
    if (params.get('tokens')) {
      const savedTokens = params.get('tokens').split(',');
      const savedAmounts = params.get('amounts') ? params.get('amounts').split(',') : [];
      batchTokenRows.innerHTML = '';
      savedTokens.forEach(function(t, i) {
        addTokenRow(t.trim(), savedAmounts[i] ? savedAmounts[i].trim() : '');
      });
    }
    if (params.get('bucket_token')) document.getElementById('bucket-token').value = params.get('bucket_token');

    // No mutual exclusivity dispatch needed — block/date unified in one field
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML
