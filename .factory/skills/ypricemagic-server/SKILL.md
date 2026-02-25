---
name: ypricemagic-server
description: Guide for working on ypricemagic-server — a multi-chain ERC-20 token price API. Use when adding endpoints, fixing price resolution bugs, adding chain support, or modifying the caching layer.
---

## Context

ypricemagic-server exposes a FastAPI HTTP API that wraps the [ypricemagic](https://github.com/BobTheBuidler/ypricemagic) library. One Docker container runs per chain; nginx routes requests by `?chain=` parameter.

## Key Files

- `src/server.py` — FastAPI app, lifespan (brownie connect + dank_mids patch), price/health endpoints, Prometheus metrics, request-ID middleware
- `src/cache.py` — diskcache wrapper; keys are `{token_lower}:{block}`; prices at a given block are immutable so cache entries never expire
- `src/params.py` — input validation for token address (EIP-55, 40 hex chars) and block number (1 to 2^63)
- `src/logger.py` — structlog configuration with secret redaction processor

## Development Workflow

```bash
uv sync --extra dev          # install deps including dev tools
uv run pytest                # run tests
uv run ruff check . --fix    # lint + autofix
uv run ruff format .         # format
uv run mypy src/             # type check
docker compose up --build    # run full stack
```

## Adding a New Chain

1. Add the chain's RPC URL env var to `env.example` and `AGENTS.md`
2. Add the chain service to `docker-compose.yml` (copy an existing chain block)
3. Add the chain name to `setup-networks.sh` EXPLORER_MAP and CATEGORY_MAP
4. Add the chain to the nginx config upstream block and location match

## Adding a New Endpoint

1. Add the route handler to `src/server.py`
2. Add input validation to `src/params.py` if needed
3. Write unit tests in `src/tests/`
4. Run `uv run python scripts/export_openapi.py` to regenerate `openapi.json`

## Important Invariants

- Cache keys use `token.lower()` — never store with mixed case
- Block-specific prices are immutable; never invalidate cache entries
- Error responses must NOT include RPC URLs or API keys (redacted by logger)
- All new endpoints must return `{"error": "..."}` format on failure with appropriate HTTP status
- The `_fetch_price` function retries up to 2 times with exponential backoff via tenacity
