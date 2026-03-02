# Validation Assertions: core-upgrade

**Area prefix**: CORE
**Scope**: Updated ypricemagic dependency, fail_to_None error handling, new query params (skip_cache, ignore_pools, silent), block_timestamp in response, enhanced /health with node sync status.

---

## 1. Dependency Update

### VAL-CORE-001: ypricemagic resolves to latest master
The `ypricemagic` git dependency re-resolves successfully and the lock file points to the latest SatoshiAndKin/ypricemagic@master commit.
Evidence: `uv.lock` shows updated commit hash; `uv sync` completes without errors.

### VAL-CORE-002: Server starts and connects with updated dependency
After updating the dependency, the FastAPI server starts, brownie connects to the network, dank_mids patches, and `from y import get_price` succeeds without import errors.
Evidence: Container logs show `startup`, `brownie_connected`, `dank_mids_patched`, `chain_connected` in sequence with no `startup_failed` error.

### VAL-CORE-003: Existing price lookup still works after dependency update
A `GET /{chain}/price?token=<valid_address>&block=<valid_block>` request returns HTTP 200 with a valid price float. Core pricing functionality is unbroken by the upgrade.
Evidence: HTTP 200 response with `{"chain": ..., "token": ..., "block": ..., "price": <float>, "cached": false}`.

---

## 2. fail_to_None Error Handling

### VAL-CORE-004: _fetch_price uses get_price(fail_to_None=True)
The `_fetch_price` function passes `fail_to_None=True` to `get_price()` so that ypricemagic returns `None` instead of raising `yPriceMagicError` for unresolvable tokens.
Evidence: Source code inspection of `_fetch_price` shows `fail_to_None=True` in the `get_price` call.

### VAL-CORE-005: Token with no price returns 404 via None path (not exception)
When `get_price(..., fail_to_None=True)` returns `None` for an unresolvable token, the server returns HTTP 404 with `{"error": "No price found for <token> at block <block>"}`.
Evidence: Request for a known-unresolvable token returns HTTP 404; server logs show `price_not_found` without exception stack traces (no `yPriceMagicError` logged).

### VAL-CORE-006: Invalid price values (NaN/Inf/negative) still rejected
Even with `fail_to_None=True`, if `get_price` returns a non-None value that is NaN, Inf, or negative, the server returns HTTP 502 with an "invalid value" error message.
Evidence: Unit test mocking `get_price` to return `float('nan')`, `float('inf')`, and `-1.0` → each yields HTTP 502.

### VAL-CORE-007: Retry logic preserved with fail_to_None
The `@retry(stop=stop_after_attempt(2))` decorator on `_fetch_price` still retries on transient errors (e.g., RPC timeouts) even though `fail_to_None=True` prevents yPriceMagicError. Other exceptions (network errors, brownie errors) still trigger retries.
Evidence: Mock `get_price` to raise `ConnectionError` on first call, succeed on second → returns 200.

---

## 3. New Query Parameters

### VAL-CORE-008: skip_cache=true bypasses server-side disk cache read
A `GET /price?token=<addr>&block=<block>&skip_cache=true` request does NOT return a cached result even if one exists. The response has `"cached": false` and the price is freshly fetched.
Evidence: Pre-populate cache for (token, block), request with `skip_cache=true` → `"cached": false`; request without `skip_cache` → `"cached": true`.

### VAL-CORE-009: skip_cache=true passes skip_cache to ypricemagic
When `skip_cache=true` is provided, the server passes `skip_cache=True` to `get_price()` so that ypricemagic's internal cache is also bypassed.
Evidence: Source code inspection shows `skip_cache=True` passed to `get_price` when the query param is set.

### VAL-CORE-010: skip_cache=true still writes result to server cache
Even when `skip_cache=true` is set, the freshly-fetched price is written back to the server-side disk cache so subsequent non-skip requests benefit.
Evidence: Request with `skip_cache=true` returns fresh price; subsequent request without `skip_cache` for same (token, block) returns `"cached": true` with same price.

### VAL-CORE-011: skip_cache defaults to false when omitted
When the `skip_cache` query param is not provided, the server uses the disk cache normally (existing behavior preserved).
Evidence: A request without `skip_cache` for a cached (token, block) returns `"cached": true`.

### VAL-CORE-012: skip_cache with invalid value returns 400
A `GET /price?token=<addr>&block=<block>&skip_cache=maybe` or `skip_cache=2` returns HTTP 400 with an error message indicating an invalid boolean value. Only `true`/`false` (case-insensitive) or `1`/`0` are accepted.
Evidence: HTTP 400 response with `{"error": ...}` mentioning invalid skip_cache value.

### VAL-CORE-013: ignore_pools accepts comma-separated addresses
A `GET /price?token=<addr>&block=<block>&ignore_pools=0xabc...,0xdef...` passes the parsed addresses as a tuple to `get_price(ignore_pools=(...))`.
Evidence: Source code shows comma-split and address validation; mock verifies `ignore_pools` kwarg passed to `get_price`.

### VAL-CORE-014: ignore_pools validates each address
If any address in `ignore_pools` is not a valid 0x-prefixed 40-hex-char address, the server returns HTTP 400 with an error identifying the invalid address.
Evidence: `GET /price?token=<valid>&block=123&ignore_pools=0xabc,notanaddress` → HTTP 400 with error mentioning the invalid pool address.

### VAL-CORE-015: ignore_pools defaults to empty when omitted
When `ignore_pools` is not provided, `get_price` is called with `ignore_pools=()` (empty tuple), matching ypricemagic's default.
Evidence: Source code inspection; existing tests still pass without ignore_pools param.

### VAL-CORE-016: ignore_pools with single address works
A `GET /price?token=<addr>&block=<block>&ignore_pools=0x<single_address>` (no comma) correctly passes a single-element tuple.
Evidence: Mock verifies `ignore_pools=(address,)` with exactly one element.

### VAL-CORE-017: silent=true suppresses ypricemagic internal logging
A `GET /price?token=<addr>&block=<block>&silent=true` passes `silent=True` to `get_price()`.
Evidence: Source code inspection shows `silent=True` passed to `get_price` when query param is set.

### VAL-CORE-018: silent defaults to false when omitted
When the `silent` query param is not provided, `get_price` is called with `silent=False` (ypricemagic default logging behavior).
Evidence: Source code inspection; default behavior preserved.

### VAL-CORE-019: All new params work together
A request combining all new params: `GET /price?token=<addr>&block=<block>&skip_cache=true&ignore_pools=0x...,0x...&silent=true` passes all three to `get_price` and returns a valid response.
Evidence: HTTP 200 with fresh price, `"cached": false`, and mock/integration test verifying all kwargs forwarded.

### VAL-CORE-020: New params are optional — existing requests unaffected
A `GET /price?token=<addr>&block=<block>` (no new params) behaves identically to pre-upgrade: cache is used, `ignore_pools=()`, `silent=False`.
Evidence: Existing test suite passes without modification; response shape unchanged.

---

## 4. Block Timestamp in Response

### VAL-CORE-021: Price response includes block_timestamp field
A successful `GET /price?token=<addr>&block=<block>` response includes a `"block_timestamp"` field containing a Unix epoch integer.
Evidence: HTTP 200 response body contains `"block_timestamp": <int>` where the int is a plausible Unix timestamp (> 1_400_000_000).

### VAL-CORE-022: block_timestamp is correct for the requested block
The `block_timestamp` value matches the actual timestamp of the requested block on-chain (as returned by `get_block_timestamp_async` or equivalent).
Evidence: Compare `block_timestamp` in response against a known block's timestamp from a block explorer (e.g., Ethereum block 18000000 = 1693958363).

### VAL-CORE-023: block_timestamp present on cache-hit responses
When a price is served from cache (`"cached": true`), the response still includes a correct `block_timestamp`.
Evidence: Request a cached price → response has both `"cached": true` and `"block_timestamp": <int>`.

### VAL-CORE-024: block_timestamp present when block is omitted (latest block)
When no `block` param is provided and the server uses `chain.height`, the response includes `block_timestamp` for that latest block.
Evidence: `GET /price?token=<addr>` → response includes `"block_timestamp"` matching the block shown in the `"block"` field.

### VAL-CORE-025: block_timestamp present on amount-based requests
When `amount` is provided, the response includes `block_timestamp` alongside the amount field.
Evidence: `GET /price?token=<addr>&block=<block>&amount=1000` → response includes both `"amount"` and `"block_timestamp"`.

### VAL-CORE-026: block_timestamp is an integer (not string or float)
The `block_timestamp` field is a JSON integer, not a string, float, or ISO-format datetime.
Evidence: JSON response parsed; `type(data["block_timestamp"])` is `int`.

---

## 5. Enhanced Health Endpoint

### VAL-CORE-027: /health reports node sync status
The `GET /health` response includes a `"synced"` field (boolean) indicating whether the node is up-to-date, as determined by `check_node_async()`.
Evidence: HTTP 200 response contains `"synced": true` or `"synced": false`.

### VAL-CORE-028: /health returns ok when node is synced
When `check_node_async()` succeeds (no exception), the response is `{"status": "ok", "chain": "...", "block": ..., "synced": true}`.
Evidence: Health check on a healthy node returns HTTP 200 with `"status": "ok"` and `"synced": true`.

### VAL-CORE-029: /health reports synced=false when node is behind
When `check_node_async()` raises `NodeNotSynced`, the health response still returns HTTP 200 but with `"synced": false` and `"status": "ok"` (the server itself is running; only the node is lagging).
Evidence: Mock `check_node_async` to raise `NodeNotSynced` → HTTP 200 with `"synced": false`.

### VAL-CORE-030: /health still returns 503 on RPC connection failure
When the brownie chain connection is completely broken (e.g., cannot reach `chain.height`), the health endpoint returns HTTP 503 with `{"status": "unhealthy", ...}` — existing behavior preserved.
Evidence: Mock `chain.height` to raise → HTTP 503 with `"status": "unhealthy"`.

### VAL-CORE-031: /health block field still present
The `"block"` field (chain height integer) is still present in the health response alongside the new `"synced"` field.
Evidence: Response contains both `"block": <int>` and `"synced": <bool>`.

### VAL-CORE-032: Per-chain /health via /{chain}/health works
Per-chain health check (`GET /ethereum/health`, `GET /arbitrum/health`, etc.) also includes the `"synced"` field.
Evidence: `GET /ethereum/health` → HTTP 200 with `"synced"` field; nginx routes correctly.

---

## 6. Backwards Compatibility

### VAL-CORE-033: Existing response fields preserved in /price
The price response retains all existing fields: `chain` (string), `token` (string), `block` (int), `price` (float), `cached` (bool), and optional `amount` (float). No fields renamed or removed.
Evidence: Existing integration tests pass; response shape is a superset of the old shape.

### VAL-CORE-034: Existing response fields preserved in /health
The health response retains `status`, `chain`, and `block` fields. The `synced` field is additive only.
Evidence: Existing health check consumers work without modification.

### VAL-CORE-035: Existing error responses unchanged
HTTP 400 (bad params), 404 (no price found), 500 (lookup failed), and 502 (invalid value) error responses retain their existing `{"error": "..."}` shape and status codes.
Evidence: Test each error path; status codes and error message patterns match pre-upgrade behavior.

### VAL-CORE-036: Cache entries are backwards compatible
Existing cached entries (pre-upgrade) can still be read. New entries (with potential block_timestamp metadata) don't break the cache read path.
Evidence: Pre-populate cache with old-format entry `{"price": 1.0, "cached_at": "..."}` → still returned as cache hit.

### VAL-CORE-037: Prometheus metrics labels unchanged
The `price_requests_total` counter labels (`chain`, `status`) and `price_request_duration_seconds` histogram labels (`chain`) are unchanged. Existing Grafana dashboards / alerting rules work.
Evidence: Inspect metric names and label sets in source; `GET /metrics` output has same metric names.

### VAL-CORE-038: nginx routing unaffected
All nginx location blocks (`/health`, `/ethereum/`, `/arbitrum/`, `/optimism/`, `/base/`, `/`) continue to proxy correctly. No changes to nginx.conf required for core-upgrade features.
Evidence: `GET /{chain}/price?...` routes to correct backend; `GET /health` aggregates via ethereum backend.

---

## 7. Edge Cases

### VAL-CORE-039: skip_cache with amount — no double cache bypass
When `amount` is provided, the server already skips cache reads (amount implies price-impact). Adding `skip_cache=true` with `amount` should still forward `skip_cache=True` to ypricemagic but not break the existing amount-skips-server-cache behavior.
Evidence: `GET /price?token=<addr>&block=<block>&amount=1000&skip_cache=true` → HTTP 200, `"cached": false`.

### VAL-CORE-040: ignore_pools with empty string is treated as no pools
`GET /price?token=<addr>&block=<block>&ignore_pools=` (empty value) should be treated as no pools to ignore, not as a parsing error.
Evidence: HTTP 200 response, `ignore_pools` passed as `()` to `get_price`.

### VAL-CORE-041: block_timestamp fetch failure is non-fatal
If `get_block_timestamp_async` fails (e.g., RPC error for that specific call), the price response should still return the price but with `block_timestamp` set to `null` rather than failing the entire request.
Evidence: Mock `get_block_timestamp_async` to raise → HTTP 200 with price present and `"block_timestamp": null`.

### VAL-CORE-042: check_node_async timeout doesn't block health
If `check_node_async()` hangs or takes excessively long, the health endpoint should time out gracefully and still return a response (possibly with `"synced": null` or omitting the field) rather than hanging indefinitely.
Evidence: Mock `check_node_async` with a long sleep → health endpoint returns within a reasonable timeout (e.g., 5s) with a fallback response.

### VAL-CORE-043: ignore_pools addresses are lowercased before passing to ypricemagic
Pool addresses in `ignore_pools` should be normalized (lowercased or checksummed consistently) before being passed to `get_price` to avoid case-sensitivity mismatches.
Evidence: `GET /price?...&ignore_pools=0xABC...` → the tuple passed to `get_price` has the address in the expected format (matching how ypricemagic handles pool addresses).

### VAL-CORE-044: Request with unknown query params is not rejected
Extra/unknown query parameters (e.g., `GET /price?token=<addr>&block=1&foo=bar`) are silently ignored, not rejected. FastAPI's default behavior.
Evidence: HTTP 200 (or appropriate price response), not HTTP 422.

### VAL-CORE-045: X-Request-ID header still propagated
The request-ID middleware continues to work: a client-supplied `X-Request-ID` header is echoed back, and a UUID is generated when not provided.
Evidence: Response includes `X-Request-ID` header matching sent value or a valid UUID.
