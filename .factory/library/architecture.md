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

## Prometheus Metrics

- `price_requests_total` Counter with labels: chain, status
- `price_request_duration_seconds` Histogram with label: chain
- Status values: ok, cache_hit, bad_request, not_found, error
