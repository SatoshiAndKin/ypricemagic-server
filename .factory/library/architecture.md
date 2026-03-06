# Architecture

## Current Architecture (Being Refactored)

```
client → nginx:8000 → ypm-ethereum:8001
                    → ypm-arbitrum:8001
                    → ypm-optimism:8001
                    → ypm-base:8001
```

FastAPI serves both API endpoints AND static files (index.html, JS, CSS).

## Target Architecture

```
client → Traefik:8000 → frontend:8080 (Svelte SPA via nginx)
                      → ypm-ethereum:8001 (API only)
                      → ypm-arbitrum:8001
                      → ypm-optimism:8001
                      → ypm-base:8001
```

**Routing rules:**
- `/{chain}/*` → strip prefix → chain backend on port 8001
- `/` (catch-all, lowest priority) → frontend on port 8080

**Frontend → Backend communication:**
- Uses `VITE_API_BASE_URL` env var (default: empty = same origin)
- All API calls prefixed with `/{chain}/` (e.g., `/ethereum/price?token=...`)
- Tokenlist proxy: `/{chain}/tokenlist/proxy?url=...`

## Key Design Decisions

- Backend is a pure JSON API — no HTML, no static files
- Frontend is a static SPA — no SSR, no backend rendering
- Traefik auto-discovers containers via Docker labels
- docker-rollout for zero-downtime deploys (no Swarm needed)
- Frontend bundled tokenlist (not fetched from backend)
