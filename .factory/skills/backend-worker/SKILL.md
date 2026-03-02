---
name: backend-worker
description: Python backend worker for ypricemagic-server features
---

# Backend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for all ypricemagic-server features: API endpoint changes, param parsing, caching, error handling, tests, nginx config, and HTML UI updates.

## Work Procedure

### 1. Understand the Feature

Read the feature description, preconditions, expectedBehavior, and verificationSteps carefully. Read AGENTS.md for conventions and boundaries. If anything is ambiguous, check the existing code for patterns.

### 2. Read Existing Code

Before writing anything, read the files you'll modify:
- `src/server.py` — endpoint definitions, error handling, response shapes
- `src/params.py` — parameter validation patterns (ParseResult, ParseError, ParseSuccess)
- `src/cache.py` — caching logic (make_key, get/set patterns)
- Relevant test files in `src/tests/`

Understand the EXISTING patterns before adding new code.

### 3. Write Tests First (TDD)

Write failing tests BEFORE implementation:
- For params: add test classes/methods in `test_params.py` following existing style (TestIsValidAddress, TestParsePriceParams patterns)
- For cache: add tests in `test_cache.py` following existing style (tmp_path + mock.patch)
- For server behavior: create `test_server.py` if it doesn't exist, using `unittest.mock.patch` to mock ypricemagic imports (they're lazy imports so patch the import path)
- Every expectedBehavior item should have at least one test

Run tests to confirm they fail: `uv run pytest -x -q`

### 4. Implement

Write the implementation to make tests pass:
- Follow existing code style exactly (double quotes, type annotations, error patterns)
- Use the `{"error": "<message>"}` format for all error responses
- Keep imports lazy for ypricemagic/brownie (inside functions)
- Type all functions with mypy-strict annotations

### 5. Run All Validators

After implementation, run ALL of these:
```bash
uv run pytest -x -q
uv run mypy src/
uv run ruff check src/
uv run ruff format --check src/
```

Fix any failures before proceeding. If ruff format fails, run `uv run ruff format src/` to auto-fix.

### 6. Manual Verification (if applicable)

For features that modify API behavior:
- If Docker stack is running, test with curl against localhost:8000
- Check response shapes, status codes, headers
- Verify backwards compatibility

For Docker rebuild features:
- Actually run `docker compose build` and `docker compose up -d`
- Wait for healthchecks and verify with curl

### 7. Commit

Commit all changes with a clear message describing what was implemented.

## Example Handoff

```json
{
  "salientSummary": "Added skip_cache, ignore_pools, and silent query params to GET /price. Added parse_bool_param and parse_ignore_pools to params.py with full validation. Server passes all three through to get_price(). skip_cache bypasses server cache read but still writes. 18 new tests in test_params.py, all passing. mypy and ruff clean.",
  "whatWasImplemented": "New optional query params (skip_cache, ignore_pools, silent) on GET /price endpoint with full validation, forwarding to ypricemagic, and cache bypass logic. Comprehensive test coverage for all param parsing edge cases.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "uv run pytest -x -q", "exitCode": 0, "observation": "65 passed in 0.08s"},
      {"command": "uv run mypy src/", "exitCode": 0, "observation": "Success: no issues found in 10 source files"},
      {"command": "uv run ruff check src/", "exitCode": 0, "observation": "All checks passed"},
      {"command": "uv run ruff format --check src/", "exitCode": 0, "observation": "4 files already formatted"}
    ],
    "interactiveChecks": [
      {"action": "curl GET /{chain}/price with skip_cache=true and valid token", "observed": "200 with cached:false, valid price"},
      {"action": "curl GET /{chain}/price with skip_cache=maybe", "observed": "400 with error about invalid boolean"}
    ]
  },
  "tests": {
    "added": [
      {"file": "src/tests/test_params.py", "cases": [
        {"name": "test_parse_bool_param_true", "verifies": "true/True/1 accepted"},
        {"name": "test_parse_bool_param_false", "verifies": "false/False/0 accepted"},
        {"name": "test_parse_bool_param_invalid", "verifies": "maybe/2/empty returns error"},
        {"name": "test_parse_ignore_pools_valid", "verifies": "comma-separated addresses parsed correctly"},
        {"name": "test_parse_ignore_pools_invalid_address", "verifies": "invalid address returns error"},
        {"name": "test_parse_ignore_pools_empty", "verifies": "empty string returns empty tuple"}
      ]}
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Feature depends on a ypricemagic function that doesn't exist or has a different signature than documented
- Docker build fails due to dependency issues you can't resolve by adjusting build constraints
- Existing tests break in ways unrelated to your changes
- A required service (Docker, nginx) is down and you can't restart it
- The feature description is contradictory or ambiguous in ways that affect implementation direction
