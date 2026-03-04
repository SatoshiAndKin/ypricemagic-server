# Architecture

Architectural decisions, patterns discovered.

---

## Request Flow

```
client -> nginx:8000 -> /<chain>/endpoint -> ypm-<chain>:8001/endpoint
```

nginx routes by chain prefix. Each chain runs its own FastAPI container with brownie connected to that chain's RPC. New endpoints (e.g. /quote) are automatically routed by existing nginx chain location blocks.

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

## Quote Architecture

The quote endpoint computes from→to pricing by:
1. Fetching USD price for `from` token via ypricemagic `get_price()`
2. Fetching USD price for `to` token via ypricemagic `get_price()`
3. Computing: `output_amount = amount * (price_from / price_to)`

There is no direct pair pricing in ypricemagic — all quotes use the divide strategy. The `route` field: "divide" for normal pairs, "identity" for same-token.

### Metric Handling Gotcha

- `src/server.py::_handle_price_error()` is currently coupled to `price_requests_total` (hardcoded increment).
- Reusing this helper from non-`/price` endpoints (e.g., `/quote`) can silently misattribute error metrics unless the helper is made metric-agnostic or endpoint-specific handling is used.

## Tokenlist Storage

All tokenlist state lives in browser localStorage:
- `tokenlists`: Array of {url, name, tokens[], enabled, isDefault, isLocal}
- `tokenlistStates`: Map of `{[url]: enabled}` used to persist toggle state
- `localTokens`: User-saved tokens from the unknown-token modal
- `theme`: Theme preference ('light', 'dark', or 'system')
- `defaultPairs`: Per-chain custom default token pairs
- Default: Uniswap tokenlist loaded from /static/tokenlists/uniswap-default.json on first visit

## Frontend Quote Form State Gotcha

- When programmatically updating `quoteFromInput` / `quoteToInput` during chain switches or default-pair restoration, reset both autocomplete instances to:
  - `suppressModal = false`
  - `wasUserEdited = false`
- This prevents stale unknown-token modal behavior from carrying over across chains after auto-filled values are applied.

### CI / Clean Checkout Note

- `static/tokenlists/uniswap-default.json` is gitignored (to avoid Droid-Shield false positives) and may be absent in clean checkouts.
- Tests handle this via `src/tests/conftest.py`: an autouse fixture writes a minimal valid tokenlist fixture only when the file is missing.

## OpenAPI Documentation Convention

`openapi.json` is a **hand-authored static file** — it is NOT auto-generated from FastAPI's `/openapi.json` endpoint. Workers adding or changing endpoints must update `openapi.json` manually to match the actual implementation.

Key differences from FastAPI auto-gen:
- Parameters have explicit descriptions and `required: true` even for `str | None` query params
- Error responses document `ErrorResponse` schema (`{"error": "..."}`) rather than FastAPI's `HTTPValidationError` for 422s (because a custom `validation_exception_handler` overrides all 422 responses project-wide)
- Both `GET /quote` (backend-local path) and `GET /{chain}/quote` (nginx-routed public path) are documented separately

## Deploy Architecture

Single VPS. Docker Compose with nginx as reverse proxy. Rolling deploy: one chain at a time, health check gating, graceful drain.
