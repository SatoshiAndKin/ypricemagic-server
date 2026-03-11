# User Testing

## Testing Surface

**Backend API:**
- Test via pytest TestClient (no Docker needed)
- If Docker running: curl to http://localhost:8000/{chain}/endpoint

**Frontend Svelte App:**
- Dev server: `cd frontend && npx vite --port 5199` → http://localhost:5199
- agent-browser can navigate and interact with the Svelte app
- All form interactions testable via browser automation
- Token list and dropdown features can be tested without backend (bundled tokenlist)

**Full Stack (Docker):**
- `docker compose up -d --build`
- Wait for health: `curl -sf http://localhost:8000/ethereum/health`
- Frontend at http://localhost:8000/
- API at http://localhost:8000/{chain}/endpoint
- Docs at http://localhost:8000/{chain}/docs

## Testing Tools

- **agent-browser**: For frontend UI testing (forms, modals, autocomplete, theme)
- **curl**: For API endpoint testing
- **pytest**: For backend unit/integration tests
- **vitest**: For frontend unit tests

## Playwright Screenshot Workaround

`playwright___browser_take_screenshot` writes to a temporary output directory (not the repo). To save a screenshot directly to the repo, use `playwright___browser_run_code` with `page.screenshot({ path: '/abs/path/to/file.png' })`.

Example:
```js
async (page) => {
  await page.screenshot({ path: '/Users/bryan/code/ypricemagic-server/docs/readme-quote-latest-block.png', fullPage: false });
}
```

## Flow Validator Guidance: Documentation and Unit Tests

This surface covers file-based checks (grep, file existence) and unit test execution. No browser is needed.

**Isolation:** No isolation needed — tests are fully read-only or isolated to test runner.

**Commands:**
- Grep README.md: `grep -n "YPM_HOST\|VIRTUAL_HOST" /Users/bryan/code/ypricemagic-server/README.md`
- Grep traefik README: `grep -n "YPM_HOST\|VIRTUAL_HOST" /Users/bryan/code/ypricemagic-server/traefik-proxy/README.md`
- Run frontend unit tests: `cd /Users/bryan/code/ypricemagic-server/frontend && npm test -- --run`
- Shared state to avoid: none

## Flow Validator Guidance: Browser UI

This surface uses agent-browser against the Vite dev server at http://localhost:5199.

**Isolation:** Assign unique session IDs per subagent. Avoid modifying localStorage in ways that affect other agents — use `window.localStorage.clear()` at start of test to reset state, then use a fresh session.

**Session IDs:** Use worker session prefix from mission worker session ID.

**What to test:**
- GitHub button presence in header, correct href, opens in new tab
- Clear button on token input fields (appears when value non-empty, clears on click)
- Token field layout (icon+symbol on label row, address-only in input)
- Arbitrum defaults to USDC→WETH (not USDC→USDC) when localStorage is clean
- Screenshot shows updated UI

**Shared state to avoid:** Don't leave localStorage in a broken state; always reset at test start.

## Known Quirks

- Backend containers take 30-60s to start (brownie network registration)
- Bucket classification is slow (10-30s per call)
- The tokenlist proxy requires a valid HTTPS URL to a tokenlist endpoint
- Amount-based price queries are not cached and may be slow
- Price lookups can timeout (10s server-side, 15s client-side)
- The /quote endpoint timed out on production — now consolidated into /price
- Production site: https://ypricemagic.stytt.com
