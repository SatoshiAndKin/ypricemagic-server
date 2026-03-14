# User Testing Guide: ypricemagic-server

## Overview

This project is a pure Python API server (FastAPI). Validation is done via pytest and code review — no browser automation needed.

## Validation Surface

No services need to be started. All assertions are verified via:
1. `uv run pytest src/tests/ -v` (automated test suite)
2. `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` (lint + types)
3. Code inspection for behavioral assertions

## Validation Concurrency

All checks are stateless (pytest, lint, code review). Multiple validators can run simultaneously without interference. Max concurrent: **5**.

## Commands

```bash
cd /Users/bryan/code/ypricemagic-server

# Run full test suite
uv run pytest src/tests/ -v

# Run specific test
uv run pytest -k 'test_name_here' -v

# Lint + format + types
uv run ruff check . && uv run ruff format --check . && uv run mypy src/
```

## Flow Validator Guidance: Automated Tests

For all milestones in this project, validation is done through automated tests, not interactive surfaces. Flow validators should:

1. Check out the implementation branch or verify current branch has the implementation
2. Run targeted pytest commands matching the evidence commands in the validation contract
3. Run `uv run pytest src/tests/ -v` for the full suite
4. Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` for lint/types
5. Check `gh pr list` for PR status, `git rev-parse --abbrev-ref HEAD` for current branch

### Isolation
All checks are read-only (no database writes, no shared state). Multiple validators can run in parallel safely.

### For check-bucket-upgrade assertions:
- VAL-CB-001 through VAL-CB-005: verify via `uv run pytest -k 'test_check_bucket' -v`
- VAL-CB-006: verify via `uv run pytest -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src/`
- VAL-CB-007: verify via `gh pr list` and `git rev-parse --abbrev-ref HEAD`
- Implementation is on branch `feat/check-bucket-metadata-and-dedup`
