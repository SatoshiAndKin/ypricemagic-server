# User Testing

Testing surface: tools, URLs, setup steps, isolation notes, known quirks.

---

## Testing Surface

- **URL**: http://localhost:8000 (nginx proxy)
- **Tool**: agent-browser (Playwright MCP) for UI interaction
- **Docker**: `docker compose up -d` must be running for full integration tests

## Setup

1. Ensure Docker is running: `docker compose ps`
2. If not running: `docker compose up -d` (wait ~60s for startup)
3. Verify: `curl -sf http://localhost:8000/ethereum/health` should return 200

## Known Quirks

- First price fetch after container start is slow (~20-75s) due to Etherscan ABI fetching
- Subsequent fetches are fast (<1s)
- Platform emulation warning (amd64 on arm64) is expected on Apple Silicon
- Etherscan rate limit (3 req/sec) can cause retry messages in container logs — this is normal
- The /favicon.ico returns 404 — not an issue
- Token input is pre-filled with DAI on load; tests that type a new query should clear the field first
- If the autocomplete "No matches" dropdown overlaps submit buttons, press `Escape` before clicking submit
- In headless runs, `Escape`/`Tab` key tests can occasionally bounce to `about:blank`; reopen `http://localhost:8000` and continue
- Tokenlist add-by-URL error banners auto-clear after ~5 seconds; capture screenshots/evidence immediately after triggering the error
- During longer automation runs, agent-browser sessions can also bounce to `about:blank` between separate command invocations; prefer grouped command sequences and re-check page URL before interacting
- The tokenlist import UI uses a dynamically-created hidden file input; direct file-upload automation may fail, but calling the app's `importTokenlistFile()` function with a synthesized `File` object is a reliable equivalent
- If containers stop mid-run, recover with `docker compose up -d` and re-check `curl -sf http://localhost:8000/ethereum/health` before resuming

## Test Isolation

Each browser session gets fresh localStorage. Use incognito/private windows if needed to test clean-slate behavior.

## Flow Validator Guidance: web-ui

- Use a dedicated browser session per flow validator worker to avoid shared UI state.
- Do not rely on prior localStorage/sessionStorage values from other validators.
- Stay within `http://localhost:8000` and do not use off-limits ports.
- For static-ui-extraction validation, avoid mutating tokenlist/localStorage settings unless required by the assigned assertion.
- Capture clear evidence for each assertion: UI snapshot/screenshot plus matching network or terminal proof where specified.
- If session instability occurs, prefer fewer larger automation steps (instead of many small calls) and include explicit waits before snapshots.
