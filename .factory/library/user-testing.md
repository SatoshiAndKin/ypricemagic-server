# User Testing

Testing surface: tools, URLs, setup steps, isolation notes, known quirks.

---

## Testing Surface

### API (curl)
- Base URL: http://localhost:8000
- Chain-specific: http://localhost:8000/{chain}/price, /prices, /check_bucket, /health
- Aggregate health: http://localhost:8000/health
- Prometheus: http://localhost:8000/metrics
- Browser UI: http://localhost:8000/
- `GET /health` response shape includes `{status, chain, block, synced}` where `synced` is `true`, `false`, or `null`

### Known good test tokens (Ethereum)
- USDC: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48
- DAI: 0x6B175474E89094C44Da98b954EedeAC495271d0F
- Known block: 18000000

### Docker Stack
- Must be running for integration tests: `docker compose up -d`
- Containers take ~60s to become healthy after start
- Build takes several minutes due to ypricemagic compilation

### Tools Available
- curl for API testing
- agent-browser for HTML UI testing
- Docker logs: `docker compose logs ypm-ethereum --tail=20`

## Known Quirks
- Token addresses may appear redacted in responses (42-char asterisks) — this is existing behavior from logger.py
- First price request after container start may be slow (cold cache, brownie warming up)
- Chain containers are independent — a test on ethereum doesn't affect arbitrum
- `/health` may take up to ~5 seconds when sync checks timeout (`check_node_async` is wrapped with a 5s timeout)
- For unresolvable-price testing, `0x0000000000000000000000000000000000000000` fails fast; some other dead addresses may run until nginx `proxy_read_timeout` (120s)
- After a long-running timed-out price request, the same chain backend may briefly return `502` via nginx until the in-flight request clears

## Flow Validator Guidance: API (curl)
- Use only your assigned assertion IDs; do not validate unrelated assertions.
- Use only your assigned data namespace token/block pairs so cache interactions remain isolated across parallel validators.
- Do not restart containers, clear cache directories, or change service state during flow tests.
- Keep tests user-surface only (HTTP calls via `curl`); do not modify app source code in flow validation.
- If an assertion depends on logs, use `docker compose logs --tail` for observation only.
