---
name: frontend-worker
description: Frontend worker for vanilla JS UI features in ypricemagic-server
---

# Frontend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for features involving the browser UI: HTML, CSS, vanilla JavaScript, static file serving, autocomplete components, modals, localStorage management, tokenlist handling.

## Work Procedure

1. **Read the feature description** carefully. Understand what assertions this feature fulfills (check the `fulfills` field).

2. **Read existing code** before writing anything:
   - `static/index.html`, `static/js/app.js`, `static/css/style.css` (after extraction)
   - `src/server.py` for the `/` endpoint and StaticFiles mount
   - `nginx.conf` for static file routing
   - `.factory/library/tokenlist-format.md` for tokenlist schema
   - `.factory/library/architecture.md` for the UI architecture

3. **Write tests first** (where applicable):
   - For Python changes (e.g., StaticFiles mount), write pytest tests that verify static file serving works
   - Run `uv run pytest` to confirm tests fail (red)
   - For JS-only changes, manual browser verification is the primary test method

4. **Implement the feature**:
   - Vanilla JS only — NO frameworks (React, Vue, etc.), NO npm, NO build tools
   - Follow existing code style: `escapeHtml()` for all user/tokenlist data, system-ui font stack, CSS custom properties
   - All tokenlist data rendered in the DOM MUST be escaped (XSS prevention)
   - Keep JavaScript in `static/js/app.js` — do not split into multiple JS files unless the feature description says to
   - Use semantic HTML elements where appropriate

5. **Run validators**:
   - `uv run pytest` — all existing tests must pass
   - `uv run ruff check .` — no lint errors
   - `uv run ruff format --check .` — formatting OK
   - `uv run mypy src/` — type checks pass (for Python changes)

6. **Manual verification** with agent-browser:
   - Navigate to http://localhost:8000
   - Test each user interaction described in the feature's `expectedBehavior`
   - For autocomplete: type in token input, verify dropdown appears, select a token, verify it fills
   - For modals: enter unknown address, verify modal appears, test each button
   - For tokenlist mgmt: add/remove/toggle lists, verify autocomplete updates
   - Take screenshots as evidence

7. **Rebuild Docker if needed**: If you changed Python files, nginx.conf, or Dockerfile:
   - `docker compose down && docker compose build && docker compose up -d`
   - Wait for health: `sleep 60 && curl -sf http://localhost:8000/ethereum/health`

## Example Handoff

```json
{
  "salientSummary": "Extracted inline HTML from server.py into static/index.html, static/js/app.js, and static/css/style.css. Added FastAPI StaticFiles mount and nginx /static/ location. All 3 forms (single price, batch, bucket) verified working via agent-browser. 236 tests pass (2 new for static serving).",
  "whatWasImplemented": "Separated the monolithic INDEX_HTML string into three static files. Created static/ directory structure with tokenlists subdirectory. Mounted StaticFiles in FastAPI at /static. Updated nginx.conf with location /static/ block. Updated Dockerfile to COPY static/ into container. Downloaded Uniswap tokenlist to static/tokenlists/uniswap-default.json. Changed / endpoint to serve static/index.html via FileResponse.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      { "command": "uv run pytest", "exitCode": 0, "observation": "236 passed, 2 new static file tests" },
      { "command": "uv run ruff check .", "exitCode": 0, "observation": "clean" },
      { "command": "uv run mypy src/", "exitCode": 0, "observation": "clean" },
      { "command": "docker compose build && docker compose up -d", "exitCode": 0, "observation": "rebuilt with static files" },
      { "command": "curl -sf http://localhost:8000/static/js/app.js | head -1", "exitCode": 0, "observation": "returns JS content" }
    ],
    "interactiveChecks": [
      { "action": "Navigate to http://localhost:8000, verify page loads with styling", "observed": "Page renders correctly with all forms visible" },
      { "action": "Submit single price form with DAI address", "observed": "Price result displayed: $1.00" },
      { "action": "Switch chain to Arbitrum, submit batch form", "observed": "Batch results table rendered correctly" },
      { "action": "Type / in block field", "observed": "Date picker appeared, clear link works" }
    ]
  },
  "tests": {
    "added": [
      { "file": "src/tests/test_static.py", "cases": [
        { "name": "test_static_js_served", "verifies": "GET /static/js/app.js returns 200 with JS content-type" },
        { "name": "test_static_css_served", "verifies": "GET /static/css/style.css returns 200" }
      ]}
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- The Docker containers won't start or are unhealthy after rebuild
- A required endpoint behavior changed unexpectedly
- The feature requires server-side changes not described in the feature description
- localStorage quota or browser API issues that can't be worked around
