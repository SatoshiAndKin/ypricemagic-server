# Architecture

Architectural decisions, patterns discovered.

---

## Container Architecture

- One container per chain, all running the same FastAPI app on port 8001
- nginx on port 8000 routes by `/{chain}/` path prefix, strips prefix before proxying
- Each container has its own diskcache volume (`cache-{chain}:/data/cache`)
- Chain identity comes from CHAIN_NAME env var

## Server Patterns

- ypricemagic/brownie imports are LAZY (inside functions) — they require network at import time
- All params come as `str | None` FastAPI Query params, parsed by params.py
- ParseResult is a union type (ParseSuccess | ParseError) — not exceptions
- Response dicts are built manually (not Pydantic models)
- Error responses use `{"error": "<message>"}` format consistently
- Cache key: `"{token_lower}:{block}"` — amount queries bypass cache entirely
- Browser UI is an inline `INDEX_HTML` string in `src/server.py` and must be updated manually when API inputs/outputs change

## Testing Constraints

- `src/tests/conftest.py` uses an `autouse=True` fixture to mock `y`, `y.time`, and `y.exceptions` in `sys.modules` to prevent real brownie/ypricemagic network initialization during tests
- FastAPI lifespan startup connects brownie networks, so endpoint-level `TestClient` tests can fail outside the Docker runtime; prefer unit tests around helper functions with explicit mocking
- `pytest` is configured with `asyncio_mode = "auto"` in `pyproject.toml`; async tests can run without explicit `@pytest.mark.asyncio` markers

## OpenAPI Artifact

- `openapi.json` at repo root is a static export and can drift from live FastAPI routes/params; regenerate it after endpoint or query parameter changes

## Prometheus Metrics

- `price_requests_total` Counter with labels: chain, status
- `price_request_duration_seconds` Histogram with label: chain
- Status values: ok, cache_hit, bad_request, not_found, error
