# User Testing Guide: ypricemagic-server

## Overview

This project is a pure Python API server (FastAPI). Validation is done via static code analysis and pytest — no browser automation needed.

## Services

No services need to be started for validation. All assertions in the `remove-skip-cache` milestone can be verified via:
1. `grep` / code inspection
2. `uv run pytest src/tests/ -x -q`
3. Python import of the FastAPI app to check `app.openapi()`

## Testing Tool

**API/code testing**: Use `curl` and shell commands (grep, python3) directly. No browser or TUI needed.

## Flow Validator Guidance: Code Static Analysis

All assertions for `remove-skip-cache` are static code checks. Flow validators should:
1. Run grep checks against `src/` to verify no `skip_cache` references
2. Run pytest via `uv run pytest src/tests/ -x -q`
3. Check OpenAPI spec via Python: `cd /Users/bryan/code/ypricemagic-server && uv run python3 -c "from src.server import app; import json; spec = app.openapi(); print('skip_cache' not in json.dumps(spec))"`
4. Check README.md and AGENTS.md for skip_cache references

### Isolation

Since all checks are read-only static analysis, there is no shared state concern. Multiple flow validators could run simultaneously without interference.

### Commands

```bash
# Check no skip_cache in src/
grep -r skip_cache /Users/bryan/code/ypricemagic-server/src/

# Run tests
cd /Users/bryan/code/ypricemagic-server && uv run pytest src/tests/ -x -q

# Check OpenAPI spec
cd /Users/bryan/code/ypricemagic-server && uv run python3 -c "from src.server import app; import json; spec = app.openapi(); print(json.dumps(spec))" | grep -c skip_cache || echo "0 occurrences"

# Check docs
grep skip_cache /Users/bryan/code/ypricemagic-server/README.md
grep skip_cache /Users/bryan/code/ypricemagic-server/AGENTS.md
```
