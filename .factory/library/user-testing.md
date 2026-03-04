# User Testing

Testing surface: tools, URLs, setup steps, isolation notes, known quirks.

---

## Testing Surface

- **URL**: http://localhost:8000 (nginx proxy)
- **Tool**: agent-browser (Playwright MCP) for UI interaction
- **API testing**: curl against http://localhost:8000
- **Docker**: `docker compose up -d` must be running for full integration tests

## Key Endpoints for Testing

- `GET /ethereum/quote?from=<addr>&to=<addr>&amount=<n>` — from→to quote
- `GET /ethereum/price/history?token=<addr>&period=7d` — historical prices
- `POST /ethereum/price/backfill` — trigger cache backfill (JSON body)
- `GET /ethereum/price?token=<addr>` — single token USD price
- `GET /ethereum/prices?tokens=<addr1>,<addr2>` — batch prices
- `GET /ethereum/check_bucket?token=<addr>` — token classification
- `GET /health` — health check

## Setup

1. Ensure Docker is running: `docker compose ps`
2. If not running: `docker compose up -d` (wait ~60s for startup)
3. Verify: `curl -sf http://localhost:8000/ethereum/health` should return 200

## Known Quirks

- First price fetch after container start is slow (~20-75s) due to Etherscan ABI fetching
- Arbitrum cold-start quote requests can exceed nginx's 120s timeout and return 502 even when `/arbitrum/health` is 200; retry after warm-up or pre-warm common pairs before strict cross-chain assertions
- Subsequent fetches are fast (<1s)
- Platform emulation warning (amd64 on arm64) is expected on Apple Silicon
- Etherscan rate limit (3 req/sec) can cause retry messages in container logs — this is normal
- The /favicon.ico returns 404 — not an issue
- Token input is pre-filled with DAI on load; tests that type a new query should clear the field first
- If the autocomplete "No matches" dropdown overlaps submit buttons, press `Escape` before clicking submit
- In headless runs, `Escape`/`Tab` key tests can occasionally bounce to `about:blank`; reopen `http://localhost:8000` and continue
- Tokenlist add-by-URL error banners auto-clear after ~5 seconds; capture screenshots/evidence immediately after triggering the error
- During longer automation runs, agent-browser sessions can also bounce to `about:blank` between separate command invocations; prefer grouped command sequences and re-check page URL before interacting
- In some runs, `agent-browser` network capture may return empty even when requests fired; use `performance.getEntriesByType('resource')` in page eval as a fallback evidence source.
- The tokenlist import UI uses a dynamically-created hidden file input; direct file-upload automation may fail, but calling the app's `importTokenlistFile()` function with a synthesized `File` object is a reliable equivalent
- If containers stop mid-run, recover with `docker compose up -d` and re-check `curl -sf http://localhost:8000/ethereum/health` before resuming
- `docker stack config -c docker-compose.yml` can fail when `depends_on` uses extended `condition` syntax (`service_healthy`); Swarm ignores `depends_on` at deploy time, so validate this separately from deploy section checks.

## Test Isolation

Each browser session gets fresh localStorage. Use incognito/private windows if needed to test clean-slate behavior.

## Flow Validator Guidance: web-ui

- Use a dedicated browser session per flow validator worker to avoid shared UI state.
- Do not rely on prior localStorage/sessionStorage values from other validators.
- Stay within `http://localhost:8000` and do not use off-limits ports.
- For static-ui-extraction validation, avoid mutating tokenlist/localStorage settings unless required by the assigned assertion.
- Capture clear evidence for each assertion: UI snapshot/screenshot plus matching network or terminal proof where specified.
- If session instability occurs, prefer fewer larger automation steps (instead of many small calls) and include explicit waits before snapshots.

## Flow Validator Guidance: deploy-cli

- Use terminal-based validation (docker compose, docker stack config, grep/curl, and docker logs) for deploy assertions.
- Keep execution scoped to `/Users/bryan/code/ypricemagic-server` and localhost services only.
- Use a unique temporary evidence namespace per validator run (for example, `/tmp/utv-zero-downtime-<group>`).
- Do not modify deployment/business logic files during validation; only read, run, and verify expected behavior.
- If Docker services are already running, reuse them instead of resetting shared volumes unless an assertion explicitly requires restart behavior.

## Flow Validator Guidance: quote-api

- Use terminal/API validation only (`curl`, `jq`, lightweight shell/Python math checks); do not use UI flows for quote-backend assertions.
- Keep traffic scoped to `http://localhost:8000/<chain>/...` and do not use off-limits ports.
- Use the assigned namespace in artifact filenames (for example, `/tmp/<namespace>-evidence.json`) so parallel validators do not overwrite each other.
- Do not mutate shared state beyond normal quote/price reads; avoid cache-clearing or docker restarts from subagents.
- If an assertion needs repeated calls (concurrency/history), keep calls within your assigned assertion set and record exact command outputs.
