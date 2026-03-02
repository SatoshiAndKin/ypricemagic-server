# Validation Assertions: New Endpoints

## Timestamp Parameter on /price

### VAL-TS-001: Unix epoch timestamp resolves to correct block
Sending `GET /price?token=DAI_ADDRESS&timestamp=1700000000` returns a 200 response where the `block` field is the block at or just before Unix epoch 1700000000, and `price` is a positive number.
Evidence: Response JSON contains `block`, `price > 0`, `chain` fields; block number matches what `get_block_at_timestamp` would return for that epoch.

### VAL-TS-002: ISO 8601 timestamp resolves to correct block
Sending `GET /price?token=DAI_ADDRESS&timestamp=2023-11-14T22:13:20Z` returns a 200 response with the same block as the equivalent Unix epoch (1700000000).
Evidence: Response JSON `block` field matches VAL-TS-001 result.

### VAL-TS-003: Timestamp and block are mutually exclusive
Sending `GET /price?token=DAI_ADDRESS&timestamp=1700000000&block=18000000` returns 400 with an error message indicating that `timestamp` and `block` cannot both be provided.
Evidence: HTTP 400 status code; response body contains `{"error": "..."}` mentioning mutual exclusivity.

### VAL-TS-004: Invalid timestamp format returns 400
Sending `GET /price?token=DAI_ADDRESS&timestamp=not-a-timestamp` returns 400 with a clear error message about invalid timestamp format.
Evidence: HTTP 400; error message references invalid timestamp.

### VAL-TS-005: Negative Unix timestamp returns 400
Sending `GET /price?token=...&timestamp=-1` returns 400 with an error about invalid timestamp.
Evidence: HTTP 400; error body present.

### VAL-TS-006: Future timestamp returns 400 or appropriate error
Sending `GET /price?token=...&timestamp=9999999999` (far future) returns an error because no block exists at that time yet, or the resolved block exceeds chain height.
Evidence: HTTP 400 or 404; error message indicates timestamp is in the future or no block found.

### VAL-TS-007: Timestamp at epoch zero returns 400
Sending `GET /price?token=...&timestamp=0` returns 400 because epoch 0 (1970-01-01) predates all EVM chains.
Evidence: HTTP 400; error references invalid or out-of-range timestamp.

### VAL-TS-008: Timestamp with no token still returns 400 for missing token
Sending `GET /price?timestamp=1700000000` (no token param) returns 400 with "Missing required parameter: token".
Evidence: HTTP 400; error matches existing missing-token validation.

### VAL-TS-009: Timestamp parameter appears in response body
When a valid timestamp query succeeds, the response includes the resolved `block` so the caller knows which block was used. Optionally, the response may also echo back the `timestamp` that was provided.
Evidence: Response JSON has `block` field with a positive integer.

### VAL-TS-010: Timestamp-resolved price is not cached with amount
When `timestamp` and `amount` are both provided, the result is not stored in the cache (consistent with existing `amount` behavior where caching is skipped).
Evidence: A second identical request still hits the backend (no `"cached": true`), or internal cache inspection shows no entry.

### VAL-TS-011: ISO 8601 timestamp without timezone is handled
Sending `GET /price?token=...&timestamp=2023-11-14T22:13:20` (no trailing Z or offset) either returns 400 asking for timezone, or defaults to UTC and resolves correctly.
Evidence: Either HTTP 400 with clear error, or HTTP 200 with correct block.

### VAL-TS-012: Decimal Unix timestamp is handled
Sending `GET /price?token=...&timestamp=1700000000.5` (fractional seconds) either truncates to integer epoch and resolves, or returns 400.
Evidence: Either HTTP 200 with correct block, or HTTP 400 with clear error.

---

## Batch Pricing GET /prices

### VAL-BATCH-001: Single token returns array of one result
Sending `GET /prices?tokens=DAI_ADDRESS` returns a 200 response with an array containing one result object with `token`, `price`, `block` fields.
Evidence: Response is a JSON array of length 1; element has expected fields.

### VAL-BATCH-002: Multiple tokens return correct array
Sending `GET /prices?tokens=DAI_ADDRESS,USDC_ADDRESS` returns a 200 response with an array of two result objects, one for each token, preserving input order.
Evidence: JSON array of length 2; `results[0].token` matches first address, `results[1].token` matches second.

### VAL-BATCH-003: Missing tokens param returns 400
Sending `GET /prices` with no `tokens` parameter returns 400 with "Missing required parameter: tokens".
Evidence: HTTP 400; error message present.

### VAL-BATCH-004: Empty tokens param returns 400
Sending `GET /prices?tokens=` returns 400.
Evidence: HTTP 400; error about missing/empty tokens.

### VAL-BATCH-005: Invalid address in token list returns 400
Sending `GET /prices?tokens=DAI_ADDRESS,INVALID` returns 400 with an error identifying the invalid address.
Evidence: HTTP 400; error references the invalid address.

### VAL-BATCH-006: Optional block param applies to all tokens
Sending `GET /prices?tokens=DAI_ADDRESS,USDC_ADDRESS&block=18000000` returns results where every element has `block: 18000000`.
Evidence: All result objects in the array have `block == 18000000`.

### VAL-BATCH-007: Optional amounts param with matching count
Sending `GET /prices?tokens=ADDR1,ADDR2&amounts=1000,500` returns results where each token's price reflects its respective amount for price-impact calculation.
Evidence: Response array has 2 elements; each element includes the respective `amount` value.

### VAL-BATCH-008: Amounts count mismatch returns 400
Sending `GET /prices?tokens=ADDR1,ADDR2&amounts=1000` (1 amount for 2 tokens) returns 400 with error about mismatched counts.
Evidence: HTTP 400; error references amounts/tokens count mismatch.

### VAL-BATCH-009: Too many tokens returns 400
Sending `GET /prices?tokens=ADDR1,ADDR2,...,ADDR101` (exceeding a reasonable max, e.g., 100) returns 400 with an error about exceeding the maximum number of tokens.
Evidence: HTTP 400; error message references token count limit.

### VAL-BATCH-010: Partial failure returns results with null prices
If one token in the batch has no price, the response still returns 200 with an array where that token's `price` is `null` (using `fail_to_None=True` from `get_prices`), and other tokens have valid prices.
Evidence: Response is 200; array contains mix of `price: <number>` and `price: null` entries.

### VAL-BATCH-011: Duplicate tokens in batch are handled
Sending `GET /prices?tokens=ADDR1,ADDR1` returns an array of 2 results (same token twice), both with valid prices.
Evidence: Response array length is 2; both have the same token address.

### VAL-BATCH-012: Batch with timestamp param works
Sending `GET /prices?tokens=ADDR1,ADDR2&timestamp=1700000000` resolves the timestamp to a block and returns prices at that block for both tokens.
Evidence: Response array has 2 elements; all have the same resolved `block`.

### VAL-BATCH-013: Batch endpoint returns correct content-type
The `/prices` endpoint returns `Content-Type: application/json`.
Evidence: Response header `Content-Type` is `application/json`.

---

## Token Classification GET /check_bucket

### VAL-BUCKET-001: Known token returns its bucket classification
Sending `GET /check_bucket?token=DAI_ADDRESS` (DAI) returns 200 with a JSON object containing a `bucket` field with a non-empty string value (e.g., "stable usd" or similar classification).
Evidence: HTTP 200; response has `{"token": "0x...", "bucket": "<string>"}`.

### VAL-BUCKET-002: Missing token param returns 400
Sending `GET /check_bucket` with no token parameter returns 400 with "Missing required parameter: token".
Evidence: HTTP 400; error message present.

### VAL-BUCKET-003: Invalid token address returns 400
Sending `GET /check_bucket?token=INVALID` returns 400 with "Invalid token address".
Evidence: HTTP 400; error references invalid address.

### VAL-BUCKET-004: Unclassifiable token returns appropriate response
Sending `GET /check_bucket?token=ZERO_ADDRESS` (not a real token) returns either a 404 or a 200 with `bucket: null` or a descriptive bucket string.
Evidence: Response status is 200 or 404; if 200, response body includes `bucket` field.

### VAL-BUCKET-005: Response includes chain field
The `/check_bucket` response includes a `chain` field matching the chain container that handled the request.
Evidence: Response JSON has `chain` field equal to the chain in the URL path (e.g., "ethereum").

### VAL-BUCKET-006: check_bucket does not require block parameter
The `/check_bucket` endpoint does not accept or require a `block` parameter (bucket classification is block-independent).
Evidence: `GET /check_bucket?token=ADDR` succeeds without any block param.

### VAL-BUCKET-007: EEE_ADDRESS (native ETH sentinel) returns a bucket
Sending `GET /check_bucket?token=EEE_ADDRESS` returns a classification for the native gas token.
Evidence: HTTP 200; `bucket` field is a non-empty string.

---

## Nginx Routing

### VAL-NGINX-001: /prices route forwards to correct chain container
Sending `GET /ethereum/prices?tokens=ADDR1` reaches the ethereum container and returns a response with `chain: "ethereum"` (or chain info in array elements).
Evidence: Response array elements contain chain data matching "ethereum".

### VAL-NGINX-002: /check_bucket route forwards to correct chain container
Sending `GET /arbitrum/check_bucket?token=ADDR` reaches the arbitrum container and returns `chain: "arbitrum"`.
Evidence: Response JSON `chain` field is "arbitrum".

### VAL-NGINX-003: Existing /price route still works after changes
Sending `GET /ethereum/price?token=ADDR` continues to work as before.
Evidence: HTTP 200 with expected price response shape.

### VAL-NGINX-004: Chain routing works for all four chains on /prices
Sending `GET /{chain}/prices?tokens=ADDR` for each of ethereum, arbitrum, optimism, base returns a valid response (not 404/502).
Evidence: HTTP 200 from all four chains.

### VAL-NGINX-005: Chain routing works for all four chains on /check_bucket
Sending `GET /{chain}/check_bucket?token=ADDR` for each of ethereum, arbitrum, optimism, base returns a valid response.
Evidence: HTTP 200 from all four chains.

### VAL-NGINX-006: Invalid chain in path returns 404
Sending `GET /polygon/prices?tokens=ADDR` (unsupported chain) returns 404 from nginx.
Evidence: HTTP 404; no backend routing occurs.

### VAL-NGINX-007: Backend down returns 502 for new endpoints
When a chain container is down, `GET /{chain}/prices?tokens=ADDR` and `GET /{chain}/check_bucket?token=ADDR` return `502` with `{"error": "Chain backend is unavailable"}`, consistent with existing error handling.
Evidence: HTTP 502; JSON body matches the existing `@backend_down` handler.

---

## HTML UI

### VAL-UI-001: UI page loads with new form sections
`GET /` returns HTML that contains form sections for: (a) single price lookup (existing), (b) batch pricing, (c) timestamp-based query, (d) token classification.
Evidence: HTML response contains form elements or section headings for each feature.

### VAL-UI-002: Timestamp field is present in the price lookup form
The existing single price form includes an optional "Timestamp" input field alongside the existing "Block Number" field.
Evidence: HTML contains an input element with id or name referencing "timestamp".

### VAL-UI-003: Timestamp and block fields are mutually exclusive in UI
When the user fills in the timestamp field, the block field is disabled or cleared (and vice versa), preventing submission of both.
Evidence: JavaScript behavior or HTML attributes enforce mutual exclusivity.

### VAL-UI-004: Batch pricing form accepts comma-separated tokens
The batch pricing section has a textarea or input for comma-separated token addresses and a submit button.
Evidence: HTML contains an input/textarea for multiple tokens and a corresponding submit button.

### VAL-UI-005: Batch pricing form includes optional amounts field
The batch pricing form has an optional field for comma-separated amounts.
Evidence: HTML contains an input for amounts with placeholder indicating comma separation.

### VAL-UI-006: Batch pricing results display as a table or list
When batch pricing returns, the UI renders results as a structured display (table or list) showing each token's address and price.
Evidence: After form submission, the result area shows multiple token/price pairs.

### VAL-UI-007: Token classification form is present
The UI includes a form section for checking a token's bucket, with a token address input and a submit button.
Evidence: HTML contains a form/section with an input for token and a submit button labeled for classification/bucket check.

### VAL-UI-008: Token classification result displays the bucket string
When the check_bucket form is submitted, the result area shows the token's classification bucket as a human-readable string.
Evidence: Result area displays the bucket name (e.g., "stable usd", "curve lp").

### VAL-UI-009: Chain selector applies to all new forms
The chain dropdown selector applies to batch pricing and check_bucket forms, not just the original single price form.
Evidence: Switching chain affects the URL used by batch pricing and check_bucket form submissions.

### VAL-UI-010: UI populates from URL query parameters
The UI reads `chain`, `token`, `tokens`, `timestamp` from URL query parameters and pre-fills corresponding form fields on page load.
Evidence: Navigating to `/?chain=arbitrum&tokens=ADDR1,ADDR2` pre-fills the batch form.

### VAL-UI-011: Error responses from new endpoints display in UI
When a batch pricing or check_bucket request fails (e.g., 400), the error message from the JSON response is displayed in the UI result area.
Evidence: Error message from server is visible in the UI, not a generic "request failed".
