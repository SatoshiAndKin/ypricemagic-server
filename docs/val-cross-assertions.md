# Cross-Area Validation Assertions

These assertions verify behaviors that span multiple subsystems of ypricemagic-server. Each asserts a cross-cutting invariant that must hold after the new features (batch pricing, `skip_cache`, `ignore_pools`, `silent`, `timestamp`, enhanced health, `check_bucket`) are integrated alongside existing behavior.

---

### VAL-CROSS-001: Existing /price response shape is unchanged for legacy callers
Any request to `GET /{chain}/price?token=0x...&block=N` that omits every new parameter (`skip_cache`, `ignore_pools`, `silent`, `timestamp`) MUST return the same JSON keys as today: `{chain, token, block, price, cached}` (plus `amount` when supplied). No new top-level keys may appear unless the caller opts in with a new parameter.
Evidence: Issue a GET `/ethereum/price?token=<DAI>&block=18000000` and assert the response body keys are exactly `{chain, token, block, price, cached}`. Compare against a recorded baseline from the current release.

---

### VAL-CROSS-002: `timestamp` and `block` are mutually exclusive with a clear 400 error
When both `timestamp` and `block` are supplied to `/price`, the server MUST return HTTP 400 with an `{"error": "..."}` body naming both parameters. The error format must use the same `{"error": "<message>"}` envelope already used by existing validation errors (e.g., "Invalid block number").
Evidence: `GET /ethereum/price?token=<DAI>&block=18000000&timestamp=1693526400` → assert 400, body matches `{"error": ...}` with a message mentioning mutual exclusivity.

---

### VAL-CROSS-003: Timestamp-resolved prices are cached by the resolved block number
When a request uses `timestamp=T` (no explicit block), the server resolves T to block B, fetches the price, and stores it in the cache keyed by `token:B`. A subsequent request with `block=B` (no timestamp) MUST return a cache hit with `"cached": true`.
Evidence: (1) `GET /price?token=<X>&timestamp=T` → note `block` in response. (2) `GET /price?token=<X>&block=<that block>` → assert `"cached": true`.

---

### VAL-CROSS-004: `skip_cache=true` bypasses read but still writes to cache
A request with `skip_cache=true` MUST always call the upstream price oracle (never return `"cached": true`). However, the fresh result MUST be written to cache so that a subsequent request without `skip_cache` returns a cache hit.
Evidence: (1) Prime cache: `GET /price?token=<X>&block=B` → cached=false. (2) `GET /price?token=<X>&block=B&skip_cache=true` → assert `cached` is false. (3) `GET /price?token=<X>&block=B` → assert `cached` is true (the write from step 2).

---

### VAL-CROSS-005: `skip_cache` + `amount` interaction — no caching at all
Today, requests with `amount` skip cache entirely (both read and write). With the new `skip_cache` param, `amount` requests with or without `skip_cache` MUST still skip cache writes (preserving current behavior where amount-based prices are not stored).
Evidence: (1) `GET /price?token=<X>&block=B&amount=1000` → cached=false. (2) `GET /price?token=<X>&block=B` → cached=false (amount response was not cached). Repeat with `skip_cache=true` and verify same outcome.

---

### VAL-CROSS-006: New endpoints are routable through nginx for all 4 chains
Every new endpoint (`/prices`, `/check_bucket`) MUST be accessible via `/{chain}/prices` and `/{chain}/check_bucket` for each of `ethereum`, `arbitrum`, `optimism`, `base`. The nginx `location /{chain}/` prefix-strip already covers `/{chain}/*`, but this must be explicitly verified for new paths.
Evidence: For each chain in [ethereum, arbitrum, optimism, base], issue `GET /{chain}/prices?tokens=<X>&block=B` and `GET /{chain}/check_bucket?token=<X>`. Assert 200 or appropriate non-502 response (502 means nginx couldn't reach backend).

---

### VAL-CROSS-007: Error response envelope is consistent across all endpoints
All error responses from `/price`, `/prices`, `/check_bucket`, and `/health` MUST use the same JSON envelope: `{"error": "<human-readable message>"}`. No endpoint may return a bare string, a `{"detail": ...}` (FastAPI default), or any other shape for application-level errors.
Evidence: For each endpoint, trigger a validation error (missing required param, invalid address, etc.) and assert the response body has exactly one key `"error"` with a string value. Verify 400, 404, 500, and 502 status codes all use this envelope.

---

### VAL-CROSS-008: Prometheus metrics track new endpoints
The `/metrics` endpoint MUST expose counters and/or histograms for the new endpoints: `price_requests_total` labels (or a new counter) must distinguish `/prices` (batch) and `/check_bucket` requests. At minimum, request count and error rate must be observable for each new endpoint type.
Evidence: (1) Hit `/prices` and `/check_bucket` endpoints. (2) Scrape `/metrics`. (3) Assert presence of counter increments with labels identifying the new endpoint or operation type. Verify the label `status` distinguishes `ok`, `bad_request`, `error`.

---

### VAL-CROSS-009: Batch /prices respects per-token caching and skip_cache
For a batch request `GET /prices?tokens=A,B,C&block=N`, if token A is cached but B and C are not, the response MUST return A from cache and fetch B and C from the oracle. If `skip_cache=true` is also passed, all three MUST be fetched fresh. Each individually fetched result MUST be written to cache.
Evidence: (1) Prime cache for token A at block N. (2) `GET /prices?tokens=A,B,C&block=N` → assert A has `cached: true`, B and C have `cached: false`. (3) `GET /prices?tokens=A,B,C&block=N&skip_cache=true` → assert all have `cached: false`. (4) `GET /price?token=B&block=N` → assert `cached: true`.

---

### VAL-CROSS-010: Batch /prices amounts array must align with tokens array
When `amounts` is provided to `/prices`, the number of amounts must equal the number of tokens. A mismatch MUST return HTTP 400 with the standard `{"error": "..."}` envelope explaining the length mismatch.
Evidence: `GET /prices?tokens=A,B&amounts=1000` (1 amount for 2 tokens) → assert 400 with `{"error": "..."}` mentioning count mismatch.

---

### VAL-CROSS-011: HTML UI exposes controls for all new parameters
The `GET /` HTML page MUST include input elements for `skip_cache`, `ignore_pools`, `silent`, and `timestamp` (in addition to the existing `chain`, `token`, `block`, `amount`). The form's JavaScript must include these params in the fetch URL when set. The batch pricing and check_bucket features should be accessible from the UI (either same form or separate section).
Evidence: Fetch `GET /` and parse the HTML. Assert presence of form fields/checkboxes for `skip_cache`, `ignore_pools`, `silent`, `timestamp`. Assert JS constructs URL with these params. Optionally check for batch/check_bucket UI elements.

---

### VAL-CROSS-012: X-Request-ID header propagates through all new endpoints
The existing middleware adds `X-Request-ID` to every response. New endpoints (`/prices`, `/check_bucket`) MUST also return this header. If the client sends `X-Request-ID`, the same value must be echoed back.
Evidence: `GET /prices?tokens=<X>&block=B` with header `X-Request-ID: test-123` → assert response header `X-Request-ID: test-123`. Repeat for `/check_bucket`.

---

### VAL-CROSS-013: Enhanced /health includes sync status without breaking existing schema
The enhanced `/health` response with node sync status MUST still include the existing fields `{status, chain, block}`. New fields (e.g., `sync_status`, `seconds_behind`) are additive. An existing client checking `response["status"] == "ok"` must continue to work.
Evidence: `GET /health` → assert response contains keys `status`, `chain`, `block` with existing semantics. Assert `status` is `"ok"` or `"unhealthy"` (not a new value). New keys are optional/additive.

---

### VAL-CROSS-014: `ignore_pools` and `silent` are forwarded to ypricemagic
When `ignore_pools=0xPool1,0xPool2` and/or `silent=true` are passed to `/price`, they MUST be forwarded as keyword arguments to the underlying `y.get_price()` call. If ypricemagic does not support these kwargs, the server should surface a clear error rather than silently dropping them.
Evidence: In a unit/integration test, mock `y.get_price` and assert it is called with `ignore_pools=[...]` and/or `silent=True` when those params are provided. Verify omitted params are not passed (not passed as None).

---

### VAL-CROSS-015: Block timestamp is included in /price response when available
The new `block_timestamp` field in the `/price` response MUST be present for both cache-hit and cache-miss paths. For cache hits, it must either be stored in the cache entry or re-derived. The timestamp should be a Unix epoch integer (or ISO string — whichever is chosen, it must be consistent across all response paths).
Evidence: (1) `GET /price?token=<X>&block=B` (cache miss) → assert `block_timestamp` is present and is an integer. (2) Same request again (cache hit) → assert `block_timestamp` is present and equals the same value. (3) Verify the type is consistent (both int or both string, never mixed).

---

### VAL-CROSS-016: CORS headers apply to all new endpoints
The existing CORS middleware (`allow_origins=["*"]`) MUST apply to new endpoints. A preflight `OPTIONS` request to `/prices` and `/check_bucket` must return `Access-Control-Allow-Origin: *`.
Evidence: `OPTIONS /prices` with `Origin: https://example.com` header → assert response includes `Access-Control-Allow-Origin: *`. Repeat for `/check_bucket`.

---

### VAL-CROSS-017: Batch /prices partial failure returns per-token errors, not a global 500
If a batch request for tokens A, B, C succeeds for A but fails for B and C, the response MUST return results for A alongside error indicators for B and C. The overall HTTP status should reflect partial success (200 with per-item errors, or a documented alternative). It must NOT return a blanket 500 that hides A's successful result.
Evidence: Request `/prices?tokens=<valid>,<nonexistent>&block=B`. Assert the response contains a successful price for the valid token and an error entry for the nonexistent token in the same response body.
