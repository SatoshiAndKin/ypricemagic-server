import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from src.cache import get_cached_price, set_cached_price
from src.params import ParseError, is_valid_address, parse_price_params

logger = logging.getLogger("ypricemagic-api")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

CHAIN_NAME = os.environ.get("CHAIN_NAME", "ethereum")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ypricemagic API starting for chain=%s", CHAIN_NAME)
    # ypricemagic connects to brownie on import via BROWNIE_NETWORK_ID env var.
    # We import it here so the connection happens at startup, not at module load.
    try:
        from y import get_price  # noqa: F401
        from brownie import chain

        logger.info("Connected to chain=%s, chain_id=%s, block=%s", CHAIN_NAME, chain.id, chain.height)
    except Exception as e:
        logger.error("Failed to initialize ypricemagic: %s", e)
        raise
    yield


app = FastAPI(title="ypricemagic API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "chain": CHAIN_NAME}


@app.get("/price")
async def price(
    token: Optional[str] = Query(None),
    block: Optional[str] = Query(None),
):
    result = parse_price_params(token, block)
    if isinstance(result, ParseError):
        return JSONResponse(status_code=400, content={"error": result.error})

    params = result.data

    from brownie import chain
    from y import get_price

    actual_block = params.block if params.block is not None else chain.height

    cached = get_cached_price(params.token, actual_block)
    if cached is not None:
        logger.info(
            "Cache hit: chain=%s token=%s block=%s price=%s",
            CHAIN_NAME, params.token[:10], actual_block, cached["price"],
        )
        return {
            "chain": CHAIN_NAME,
            "token": params.token,
            "block": actual_block,
            "price": cached["price"],
            "cached": True,
        }

    start = time.monotonic()
    try:
        p = get_price(params.token, actual_block)
        if p is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"No price found for {params.token} at block {actual_block}"},
            )
        price_float = float(p)
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "Price lookup failed: chain=%s token=%s block=%s error=%s (%dms)",
            CHAIN_NAME, params.token[:10], actual_block, e, duration_ms,
        )
        return JSONResponse(status_code=500, content={"error": str(e)})

    duration_ms = int((time.monotonic() - start) * 1000)
    set_cached_price(params.token, actual_block, price_float)
    logger.info(
        "Price: chain=%s token=%s block=%s price=%s (%dms)",
        CHAIN_NAME, params.token[:10], actual_block, price_float, duration_ms,
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
async def index():
    return INDEX_HTML
