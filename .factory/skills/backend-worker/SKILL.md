---
name: backend-worker
description: Python backend worker for ypricemagic-server API changes
---

# Backend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for backend API features: endpoint changes, param validation, OpenAPI config, Sentry integration, env documentation, tests.

## Work Procedure

### 1. Understand the Feature

Read the feature description, preconditions, expectedBehavior, verificationSteps, and fulfills carefully. Read AGENTS.md for boundaries. Check `.factory/library/architecture.md` for existing patterns.

### 2. Read Existing Code

Before writing anything, read the files you'll modify:
- `src/server.py` — endpoint definitions, middleware, error handling, Prometheus metrics
- `src/params.py` — parameter validation (PriceParams, BatchParams, QuoteParams)
- `src/cache.py` — caching logic
- `src/tests/test_server.py` and `src/tests/test_params.py` — existing test patterns

Key patterns:
- Error responses use `{"error": "<message>"}` envelope format
- All ypricemagic/brownie imports are lazy (inside functions)
- Type annotations on all public functions (mypy strict)
- `_fetch_price()` and `_fetch_batch_prices()` are the core price-fetching functions
- Quote logic is currently in the `/quote` endpoint handler

### 3. Write Tests First (TDD)

Write failing tests BEFORE implementation:
- Follow existing test patterns in `src/tests/test_server.py` and `src/tests/test_params.py`
- Use `unittest.mock.patch` for ypricemagic mocks
- Each `expectedBehavior` item needs at least one test
- For removed features, write tests that assert 404/removal

Run: `uv run pytest -x -q` — confirm new tests fail, existing unrelated tests pass.

### 4. Implement

- Follow existing code style exactly (double quotes, 4-space indent, 100 char lines)
- Use ruff format conventions
- When modifying endpoints, ensure backward compatibility where specified
- For timeout wrapping: use `asyncio.wait_for(coro, timeout=10.0)`, catch `asyncio.TimeoutError`
- For Sentry: `sentry_sdk.init()` before FastAPI app creation, gated on `SENTRY_DSN` env var
- For OpenAPI: use FastAPI's built-in auto-generation, set `version=` from `importlib.metadata`

### 5. Run All Validators

```bash
uv run pytest -x -q
uv run mypy src/
uv run ruff check src/
uv run ruff format --check src/
```

Fix all failures. Auto-fix formatting with `uv run ruff format src/` if needed.

### 6. Manual Verification

For API behavior changes:
- Use `uv run pytest` (covers API via httpx TestClient)
- For OpenAPI changes: verify `/openapi.json` via TestClient returns correct spec
- For removed routes: verify 404 via TestClient
- Check Prometheus /metrics if counters changed

### 7. Commit

Commit all changes with a clear message.

## Example Handoff

```json
{
  "salientSummary": "Removed static file serving from FastAPI (GET /, /static mount). Verified /docs and /redoc are accessible. Updated CORS to use CORS_ORIGINS env var. Removed test_static.py tests for removed features. Added 4 new tests for docs/redoc/openapi endpoints. 301 tests pass, mypy and ruff clean.",
  "whatWasImplemented": "Removed StaticFiles mount and GET / FileResponse route from server.py. Removed FileResponse and StaticFiles imports. Verified FastAPI's built-in /docs, /redoc, /openapi.json are active. Updated CORSMiddleware to read CORS_ORIGINS from env (comma-separated, defaults to *). Removed 4 static file tests, added 4 docs endpoint tests.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "uv run pytest -x -q", "exitCode": 0, "observation": "301 passed"},
      {"command": "uv run mypy src/", "exitCode": 0, "observation": "Success"},
      {"command": "uv run ruff check src/", "exitCode": 0, "observation": "All checks passed"},
      {"command": "uv run ruff format --check src/", "exitCode": 0, "observation": "formatted"}
    ],
    "interactiveChecks": [
      {"action": "curl GET /docs via TestClient", "observed": "200 HTML with Swagger UI"},
      {"action": "curl GET / via TestClient", "observed": "404 not found"},
      {"action": "curl GET /static/js/app.js via TestClient", "observed": "404 not found"}
    ]
  },
  "tests": {
    "added": [
      {"file": "src/tests/test_server.py", "cases": [
        {"name": "test_docs_accessible", "verifies": "GET /docs returns 200"},
        {"name": "test_redoc_accessible", "verifies": "GET /redoc returns 200"},
        {"name": "test_openapi_json", "verifies": "GET /openapi.json returns valid JSON"},
        {"name": "test_static_removed", "verifies": "GET / and /static return 404"}
      ]}
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Feature depends on ypricemagic internals that don't match expected behavior
- Docker build fails due to dependency issues
- Existing tests break for reasons unrelated to this feature
- Feature description is ambiguous about whether to keep or remove something
