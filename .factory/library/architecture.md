# Architecture

Architectural decisions, patterns discovered.

---

## Request Flow

```
client -> nginx:8000 -> /<chain>/endpoint -> ypm-<chain>:8001/endpoint
```

nginx routes by chain prefix. Each chain runs its own FastAPI container with brownie connected to that chain's RPC. New endpoints (quote, price/history, price/backfill) are automatically routed by existing nginx chain location blocks.

## UI Architecture

```
client -> nginx:8000 -> /static/* -> static files (index.html, js/app.js, css/style.css)
                     -> /         -> serves index.html
                     -> /<chain>/ -> proxied to chain container
```

The UI is vanilla JS served as static files. No build step, no framework.

### Frontend File Structure
- `static/index.html` — page structure, forms, modals, inline theme-init script in <head>
- `static/js/app.js` — all JavaScript logic
- `static/css/style.css` — all styles, CSS custom properties for theming

### External Libraries
- lightweight-charts (TradingView): loaded from CDN via `<script>` tag in index.html. ~45KB. Provides `LightweightCharts` global.

## Quote Architecture

The quote endpoint computes from→to pricing by:
1. Fetching USD price for `from` token via ypricemagic `get_price()`
2. Fetching USD price for `to` token via ypricemagic `get_price()`
3. Computing: `output_amount = amount * (price_from / price_to)`

There is no direct pair pricing in ypricemagic — all quotes use the divide strategy. The `route` field: "divide" for normal pairs, "identity" for same-token.

## Historical Price Data

- **History endpoint**: Reads from diskcache. Scans cached entries for a token within the requested time range, returning them at the appropriate granularity (hourly for ≤7d, daily for >7d).
- **Backfill endpoint**: Populates cache by fetching prices at regular block intervals using `asyncio.create_task()` (non-blocking). Returns 202 immediately.

## Tokenlist Storage

All tokenlist state lives in browser localStorage:
- `tokenlists`: Array of {url, name, tokens[], enabled, isDefault, isLocal}
- `tokenlistStates`: Map of `{[url]: enabled}` used to persist toggle state
- `localTokens`: User-saved tokens from the unknown-token modal
- `theme`: Theme preference ('light', 'dark', or 'system')
- `defaultPairs`: Per-chain custom default token pairs
- Default: Uniswap tokenlist loaded from /static/tokenlists/uniswap-default.json on first visit

### CI / Clean Checkout Note

- `static/tokenlists/uniswap-default.json` is gitignored (to avoid Droid-Shield false positives) and may be absent in clean checkouts.
- Tests handle this via `src/tests/conftest.py`: an autouse fixture writes a minimal valid tokenlist fixture only when the file is missing.

## Deploy Architecture

Single VPS. Docker Compose with nginx as reverse proxy. Rolling deploy: one chain at a time, health check gating, graceful drain.
