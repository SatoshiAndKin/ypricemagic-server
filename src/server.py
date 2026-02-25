import math
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from src.cache import get_cached_price, set_cached_price
from src.logger import configure_logging, get_logger
from src.params import ParseError, parse_price_params

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

# Expose Prometheus metrics at /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/health")
async def health() -> dict[str, Any]:
    try:
        from brownie import chain

        height = chain.height
        return {"status": "ok", "chain": CHAIN_NAME, "block": height}
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content={"status": "unhealthy", "chain": CHAIN_NAME, "error": "RPC connection failed"},
        )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
async def _fetch_price(token: str, block: int) -> float:
    from y import get_price

    p = await get_price(token, block, sync=False)  # type: ignore[call-overload]
    if p is None:
        raise ValueError(f"No price returned for {token} at block {block}")
    price_float = float(p)
    if math.isnan(price_float) or math.isinf(price_float):
        raise ValueError(f"Invalid price value {p} for {token} at block {block}")
    if price_float < 0:
        raise ValueError(f"Negative price {price_float} for {token} at block {block}")
    return price_float


@app.get("/price")
async def price(
    token: str | None = Query(None),
    block: str | None = Query(None),
) -> Any:
    result = parse_price_params(token, block)
    if isinstance(result, ParseError):
        price_requests_total.labels(chain=CHAIN_NAME, status="bad_request").inc()
        return JSONResponse(status_code=400, content={"error": result.error})

    params = result.data

    from brownie import chain as brownie_chain

    actual_block = params.block if params.block is not None else brownie_chain.height

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
        }

    start = time.monotonic()
    try:
        price_float = await _fetch_price(params.token, actual_block)
    except (RetryError, ValueError) as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        inner = e.__cause__ if isinstance(e, RetryError) else e
        msg = str(inner)
        if "No price returned" in msg:
            price_requests_total.labels(chain=CHAIN_NAME, status="not_found").inc()
            logger.warning("price_not_found", token=params.token[:10], block=actual_block)
            return JSONResponse(
                status_code=404,
                content={"error": f"No price found for {params.token} at block {actual_block}"},
            )
        price_requests_total.labels(chain=CHAIN_NAME, status="error").inc()
        logger.error(
            "price_lookup_failed",
            token=params.token[:10],
            block=actual_block,
            duration_ms=duration_ms,
        )
        if "Invalid price value" in msg or "Negative price" in msg:
            return JSONResponse(
                status_code=502,
                content={
                    "error": f"Price source returned invalid value for {params.token} at block {actual_block}"
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Price lookup failed for {params.token} at block {actual_block}. Check server logs."
            },
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        price_requests_total.labels(chain=CHAIN_NAME, status="error").inc()
        logger.error(
            "price_lookup_error",
            token=params.token[:10],
            block=actual_block,
            duration_ms=duration_ms,
            error=type(e).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Price lookup failed for {params.token} at block {actual_block}. Check server logs."
            },
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    set_cached_price(params.token, actual_block, price_float)
    price_requests_total.labels(chain=CHAIN_NAME, status="ok").inc()
    price_request_duration_seconds.labels(chain=CHAIN_NAME).observe(duration_ms / 1000)
    logger.info(
        "price_fetched",
        chain=CHAIN_NAME,
        token=params.token[:10],
        block=actual_block,
        price=price_float,
        duration_ms=duration_ms,
    )

    return {
        "chain": CHAIN_NAME,
        "token": params.token,
        "block": actual_block,
        "price": price_float,
        "cached": False,
    }


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
    form { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .form-group { margin-bottom: 16px; }
    label { display: block; font-weight: 600; margin-bottom: 6px; color: #555; }
    input, select { width: 100%; padding: 10px; font-size: 14px; border: 1px solid #ddd; border-radius: 4px; }
    input { font-family: monospace; }
    input:focus, select:focus { outline: none; border-color: #0066cc; }
    button { padding: 12px 24px; font-size: 16px; cursor: pointer; background: #0066cc; color: white; border: none; border-radius: 4px; }
    button:hover { background: #0052a3; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    #result { background: #1e1e1e; color: #d4d4d4; padding: 20px; border-radius: 8px; display: none; }
    #result.show { display: block; }
    .error { color: #e74c3c; }
    .result-header { color: #888; margin-bottom: 12px; font-size: 14px; }
    .field { margin-bottom: 12px; }
    .field-label { color: #888; font-size: 12px; text-transform: uppercase; }
    .field-value { color: #4ec9b0; word-break: break-all; }
    .field-value.number { color: #b5cea8; font-size: 24px; }
    .field-value .dim { color: #888; font-size: 11px; }
  </style>
</head>
<body>
  <h1>ypricemagic Price Lookup</h1>

  <form id="form">
    <div class="form-group">
      <label for="chain">Chain</label>
      <select id="chain">
        <option value="ethereum">Ethereum</option>
        <option value="arbitrum">Arbitrum</option>
        <option value="optimism">Optimism</option>
        <option value="base">Base</option>
        <option value="polygon">Polygon</option>
      </select>
    </div>
    <div class="form-group">
      <label for="token">Token Address</label>
      <input type="text" id="token" placeholder="0x..." value="0x6B175474E89094C44Da98b954EedeAC495271d0F">
    </div>
    <div class="form-group">
      <label for="block">Block Number (optional, blank for latest)</label>
      <input type="text" id="block" placeholder="e.g. 18000000">
    </div>
    <button type="submit" id="submit">Get Price</button>
  </form>

  <div id="result"></div>

  <script>
    const form = document.getElementById('form');
    const result = document.getElementById('result');
    const submit = document.getElementById('submit');

    function showResult(data) {
      result.className = 'show';
      result.innerHTML = `
        <div class="result-header">Price Result</div>
        <div class="field">
          <div class="field-label">Chain</div>
          <div class="field-value">${data.chain}</div>
        </div>
        <div class="field">
          <div class="field-label">Token</div>
          <div class="field-value"><span class="dim">${data.token}</span></div>
        </div>
        <div class="field">
          <div class="field-label">Block</div>
          <div class="field-value">${data.block}</div>
        </div>
        <div class="field">
          <div class="field-label">Price (USD)</div>
          <div class="field-value number">${data.price}</div>
        </div>
        <div class="field">
          <div class="field-label">Cached</div>
          <div class="field-value">${data.cached ? 'yes' : 'no'}</div>
        </div>
      `;
    }

    function showError(msg) {
      result.className = 'show';
      result.innerHTML = '<div class="error">' + msg + '</div>';
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const chain = document.getElementById('chain').value;
      const token = document.getElementById('token').value.trim();
      const block = document.getElementById('block').value.trim();

      submit.disabled = true;
      submit.textContent = 'Fetching...';
      result.className = 'show';
      result.innerHTML = '<div class="result-header">Fetching price...</div>';

      try {
        const params = new URLSearchParams({ chain, token });
        if (block) params.set('block', block);

        const res = await fetch('/price?' + params.toString());
        const data = await res.json();

        if (data.error) {
          showError(data.error);
        } else {
          showResult(data);
          const url = new URL(window.location.href);
          url.searchParams.set('chain', chain);
          url.searchParams.set('token', token);
          if (block) url.searchParams.set('block', block);
          else url.searchParams.delete('block');
          window.history.replaceState({}, '', url.toString());
        }
      } catch (err) {
        showError('Request failed: ' + err.message);
      } finally {
        submit.disabled = false;
        submit.textContent = 'Get Price';
      }
    });

    const params = new URLSearchParams(window.location.search);
    if (params.get('chain')) document.getElementById('chain').value = params.get('chain');
    if (params.get('token')) document.getElementById('token').value = params.get('token');
    if (params.get('block')) document.getElementById('block').value = params.get('block');
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML
