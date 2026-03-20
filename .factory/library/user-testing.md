# User Testing Guide: ypricemagic-server

## Overview

This project has a Python API server (FastAPI) backend and a Svelte 5 frontend. Validation uses both automated tests and browser automation.

## Validation Surface

### Backend
- `uv run pytest src/tests/ -v` (automated test suite)
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` (lint + types)

### Frontend
- `cd frontend && npm test -- --run` (vitest test suite)
- `cd frontend && npm run check` (svelte-check / TypeScript)
- `cd frontend && npm run build` (production build)
- agent-browser against http://localhost:8000 (live app running via Docker)

## Validation Concurrency

Backend checks are stateless (pytest, lint, code review). Frontend unit tests are also stateless. Browser tests need the Docker stack running (already up on ports 8000/8080). Max concurrent validators: **5** (36GB RAM, 14 cores).

## Commands

```bash
cd /Users/bryan/code/ypricemagic-server

# Backend
uv run pytest src/tests/ -v
uv run pytest -k 'test_name_here' -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src/

# Frontend
cd frontend && npm test -- --run
cd frontend && npm run check
cd frontend && npm run build
```

## Flow Validator Guidance

### Backend assertions (VAL-WARM-*, VAL-UPDATE-*, VAL-QUAL-001)
Verify via pytest and code inspection. No running server needed.

### Frontend assertions (VAL-UNK-*, VAL-QUAL-002)
Verify via vitest, svelte-check, and build. For VAL-UNK-001/002/003, also use agent-browser against http://localhost:8000.

### Cross-area assertions (VAL-CROSS-001)
Use agent-browser against http://localhost:8000 for the full unknown-token flow.

### Browser testing notes
- The Docker stack is already running: Traefik on :8000, frontend on :8080 (internal), backend on :8001 (internal)
- Navigate to http://localhost:8000 for the full app
- **IMPORTANT**: The Docker frontend container may be built before the latest commits. If testing new frontend features, start the Vite dev server: `cd frontend && npm run dev -- --port 5173` and test against http://localhost:5173 instead. The Vite dev server proxies API calls to localhost:8000.
- Use a known-unknown token address for testing: `0x6399c842dd2be3de30bf99bc7d1bbf6fa3650e70` (PREMIA token, returns symbol=PREMIA/name=Premia/decimals=18 from check_bucket)
- The check_bucket call may take several seconds for unknown tokens

### Isolation
Backend checks are read-only. Browser tests modify localStorage (local tokens) but each validator instance can use its own browser context.
