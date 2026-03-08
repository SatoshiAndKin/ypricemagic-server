---
name: frontend-worker
description: Svelte 5 + Vite + TypeScript frontend worker for ypricemagic-server
---

# Frontend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for all Svelte frontend features: project scaffolding, components, API client, tokenlist engine, autocomplete, forms, modals, theming, URL state, localStorage, tests, and build config.

## Technology Stack

- **Svelte 5** with runes syntax (`$state`, `$derived`, `$effect`, `$props`)
- **Vite** for dev server and production builds
- **TypeScript** for all code
- **Vitest** for unit tests
- **No additional UI frameworks** — use native Svelte components and CSS

## Critical Svelte 5 Patterns

- Use `let x = $state(value)` for reactive state, NOT `let x = value` with `$:`
- Use `let { prop } = $props()` for component props, NOT `export let prop`
- Use `onclick={handler}` for events, NOT `on:click={handler}`
- Use `$derived(expr)` for computed values, NOT `$: derived = expr`
- Use `$state.raw(value)` for large non-proxied objects (API responses)
- Use `{#snippet name()}...{/snippet}` + `{@render name()}` instead of `<slot>`
- Effects (`$effect`) are escape hatches — prefer `$derived` where possible

## Work Procedure

### 1. Understand the Feature

Read the feature description, preconditions, expectedBehavior, verificationSteps, and fulfills carefully. Read AGENTS.md for conventions. Check `.factory/library/` for relevant context.

### 2. Read Existing Code

**For the first feature (scaffold):**
- Read the current `static/index.html`, `static/js/app.js`, `static/css/style.css` to understand what to port
- Read `.factory/library/architecture.md` and `.factory/library/tokenlist-format.md`

**For subsequent features:**
- Read the existing `frontend/` directory structure
- Read any components already created
- Read `frontend/src/lib/` for shared utilities and stores

### 3. Reference the Original Implementation

The vanilla JS app at `static/js/app.js` (~2257 lines) is the behavioral specification. When porting a feature:
- Read the relevant section of `app.js` to understand EXACT behavior
- Match ALL edge cases, error handling, and state management
- Preserve localStorage key names and data schemas exactly:
  - `theme` — "light" | "dark" (removed for "system")
  - `defaultPairs` — `{ [chain]: { from: addr, to: addr } }`
  - `tokenlists` — array of tokenlist objects with tokens
  - `localTokens` — array of token objects
  - `tokenlistStates` — `{ [key]: boolean }`

### 4. Write Tests First (TDD)

Write Vitest tests BEFORE implementation for:
- API client functions (URL construction, response parsing, error handling)
- Tokenlist index building and search
- URL state parsing
- Any pure logic functions

Test file convention: `*.test.ts` next to the module being tested, or in `__tests__/`.

Run: `cd frontend && npm test -- --run` to verify tests fail.

### 5. Implement

**Project structure** (for scaffold feature):
```
frontend/
  src/
    lib/
      api.ts          — API client (configurable base URL)
      types.ts        — TypeScript interfaces for API responses
      stores/         — Shared state (tokenlists, theme, chain)
      components/     — Reusable Svelte components
    routes/           — Page components (if using routing)
    App.svelte        — Root component
    main.ts           — Entry point
    app.css           — Global styles (CSS custom properties for theming)
  public/
    tokenlists/
      uniswap-default.json  — Bundled default tokenlist
  index.html          — HTML shell with inline theme script
  vite.config.ts      — Vite config with dev proxy
  tsconfig.json
  package.json
```

**API client pattern:**
```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function fetchQuote(chain: string, params: QuoteParams) {
  const url = `${API_BASE}/${chain}/quote?${new URLSearchParams(...)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }
  return res.json();
}
```

**Theme system:**
- Inline `<script>` in `index.html` `<head>` (before CSS) for FOUC prevention
- CSS custom properties with `[data-theme="dark"]` and `[data-theme="light"]`
- Svelte theme store syncs with localStorage and `data-theme` attribute

**Autocomplete component:**
- Debounced search (150ms)
- Keyboard navigation (ArrowUp/Down, Enter, Escape, Tab)
- Mouse hover highlight, mousedown selection (preventDefault to prevent blur)
- Token icon with onerror fallback
- "No matches" text when empty results
- Disambiguation badges when symbols collide

**Important behaviors to preserve:**
- Amount defaults to '1' on quote submit if empty
- "/" in block field switches to datetime-local input type
- Unknown token modal suppressed for URL-populated and chain-change values
- Batch form does NOT check unknown tokens (unlike quote/bucket)
- Chain mismatch warning in results
- 3 parallel API calls on quote submit (quote + 2 price lookups)
- Live age counter with interval cleanup
- HTML escaping for all dynamic content

### 6. Run Validators

```bash
cd frontend && npm run build
cd frontend && npx svelte-check --tsconfig ./tsconfig.json
cd frontend && npm test -- --run
```

All must pass. Fix any TypeScript errors or test failures.

### 7. Manual Verification with agent-browser

For UI features, verify with agent-browser:
- Start the dev server: `cd frontend && npm run dev` (port 5173)
- Navigate to http://localhost:5173
- Test each interaction in the feature's `expectedBehavior`
- Take snapshots as evidence
- Kill the dev server when done

### 8. Commit

Commit all changes with a clear message.

## Example Handoff

```json
{
  "salientSummary": "Built quote form component with from/to autocomplete, amount warning, block/date picker, loading states, error display, trade path rendering, USD prices, live age counter, and chain mismatch warning. 12 Vitest tests for API client and URL construction. svelte-check clean. Verified all interactions via agent-browser.",
  "whatWasImplemented": "QuoteForm.svelte with full feature parity: token inputs with Autocomplete component, amount field with cache warning, block/date picker (/ trigger, Clear link), loading state (Fetching..., disabled button), error display, result rendering with conversion rate + USD prices + trade path + live age counter + chain mismatch warning. Reset Defaults button. Unknown token modal integration. 3 parallel API calls (quote + 2 prices). API client functions in api.ts with error envelope handling.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "cd frontend && npm run build", "exitCode": 0, "observation": "Build successful, dist/ created"},
      {"command": "cd frontend && npx svelte-check", "exitCode": 0, "observation": "0 errors"},
      {"command": "cd frontend && npm test -- --run", "exitCode": 0, "observation": "12 tests passed"}
    ],
    "interactiveChecks": [
      {"action": "Navigate to http://localhost:5173, fill quote form, submit", "observed": "Quote result displayed with conversion rate, USD prices, trade path, age counter"},
      {"action": "Type / in block field", "observed": "Switched to date picker, Clear link appeared"},
      {"action": "Enter amount, verify warning", "observed": "Yellow cache warning shown"},
      {"action": "Click Reset Defaults", "observed": "Tokens reverted to factory defaults for current chain"},
      {"action": "Submit with unknown token address", "observed": "Unknown token modal appeared with Save/Continue/Reject options"}
    ]
  },
  "tests": {
    "added": [
      {"file": "frontend/src/lib/api.test.ts", "cases": [
        {"name": "fetchQuote builds correct URL", "verifies": "URL includes chain, from, to, amount params"},
        {"name": "fetchQuote handles error envelope", "verifies": "Throws with error message from JSON body"},
        {"name": "fetchQuote handles non-JSON error", "verifies": "Throws with HTTP status when body is not JSON"}
      ]}
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- A required Svelte 5 API or pattern doesn't work as expected
- The backend API response shape differs from what's documented
- Node.js / npm dependency issues that can't be resolved
- Feature requires backend changes not in the feature description
- The existing vanilla JS behavior is ambiguous and the feature description doesn't clarify
