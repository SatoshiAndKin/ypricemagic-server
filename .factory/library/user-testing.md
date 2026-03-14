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
