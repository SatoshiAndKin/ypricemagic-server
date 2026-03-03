# Architecture

Architectural decisions, patterns discovered.

---

## Request Flow

```
client -> nginx:8000 -> /<chain>/endpoint -> ypm-<chain>:8001/endpoint
```

nginx routes by chain prefix. Each chain runs its own FastAPI container with brownie connected to that chain's RPC.

## UI Architecture (after extraction)

```
client -> nginx:8000 -> /static/* -> static files (index.html, js/app.js, css/style.css)
                     -> /         -> serves index.html
                     -> /<chain>/ -> proxied to chain container
```

The UI is vanilla JS served as static files. No build step, no framework.

## Tokenlist Storage

All tokenlist state lives in browser localStorage:
- `tokenlists`: Array of {url, name, tokens[], enabled, isDefault, isLocal}
- `tokenlistStates`: Map of `{[url]: enabled}` used to persist toggle state
- `localTokens`: User-saved tokens from the unknown-token modal
- Default: Uniswap tokenlist loaded from /static/tokenlists/uniswap-default.json on first visit

## Deploy Architecture

Single VPS. Docker Compose with nginx as reverse proxy. Rolling deploy: one chain at a time, health check gating, graceful drain.
