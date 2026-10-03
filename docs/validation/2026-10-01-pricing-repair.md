# Pricing, startup, and validation repair

Updated October 2, 2026. The repair is in progress. Production acceptance has not
been claimed. The first repair pair deployed server
`be640a5bc2f0e1db3ced13b29b0f77fb7a5b4de7` with pricing fork
`073c7ac801ca36128eb27efc64031851ab6f2101`. Its failed acceptance runs and remaining
gates are recorded below.

## Reproduced failures and provenance

Five routing/cache/startup regression tests failed against the deployed server:
required warmup cancellation returned normally; ambiguous persisted errors were
reused; transient failures entered the 404 cache; timeouts were attempted twice;
and slow cancellation delayed the HTTP timeout response. These predate PRs
152/156/157: signal handling was introduced in PRs 137/139, error caching in PR
124, and the lookup timeout in PR 58. Classification timeouts and connectivity
failures also returned 500; four route-level cases reproduced that behavior
before repair. The handler dates to commit `80049c1`, before the recent PRs,
and now preserves 504/502 statuses.

Six pricing-fork regressions failed against the deployed revision: broader
factory coverage was ignored for both token topic positions and alternatives;
disjoint scans falsely claimed the gap; and plDAI/plUSDC mappings were absent.
Token discovery's repeated scans were exposed by fork PR 46. The cache coverage
and missing mapping behavior also exist in its parent, the PR 43 merge.
Chainlink feed selection awaited the entire feed catalog before querying its
authoritative registry. An empty-cache candidate reproduced historical USDT
HTTP 504 responses at the single 300-second deadline. The event-first selection
order dates to commit `50e1d057` (September 11), before the recent fork PRs;
it was exposed by the smaller log ranges and concurrent cold warmup.
The smoke validator's xPREMIA address had no code; the real deployment is
`0x16f9D564Df80376C61AC914205D3fDfF7057d610`. The no-code address remains a
separate expected-unavailable test.

## Request and container limits

All price, batch, and classification requests have one 300-second routing budget,
including block/timestamp resolution, admission, retry backoff, and metadata.
HTTP 504 does not wait for cancellation cleanup. Lookup work retains its active
slot until cleanup completes, and is observed by the backend supervisor.
Two uncached requests can run and 32 can queue per backend. Overload returns 503
with `Retry-After: 5`; cache hits and health bypass the lookup queue.
Only definitive unavailable prices enter the error cache; legacy ambiguous
entries are misses. Startup, signal-driven draining, and shutdown return 503
health. SIGTERM chains and restores Uvicorn's actual handlers.

Each backend has an 8 GiB memory limit with swap disabled. The 600-second health
start period and existing stop grace are preserved. Browser and smoke clients
allow 315 seconds to receive the server's 300-second timeout response.

## Validation completed so far

- Server: 333 tests passed; 89% coverage. Ruff, format, strict mypy, deptry passed.
  Exact historical benchmark comparisons reject a one-ULP mismatch on either
  chain; mixed batches compare both amount entries to their individual quotes.
- Real process SIGTERM during warmup and after readiness passed; cancelled startup
  did not log readiness, and both processes stopped within five seconds.
- Saturation test fills exactly two active slots and 32 queued requests; additional
  work returns 503 while cached price and health requests return 200.
- Frontend: Svelte check, 89 tests, and production build passed.
- Fork: the earlier targeted native Python 3.12 run passed 404 tests,
  strict mypy covered all 240 Python files, and ten extension imports were
  confirmed to resolve to compiled `.so` modules. Two native xPREMIA
  deployment-boundary checks also passed. Black/isort checks cover the full trees.
- A full native run passed 2,259 tests with 17 skips and no OOM. Its source
  predates the final native-call transport and shared broad factory repairs.
  The latest runtime-source full suite passed 2,291 tests with 17 skips and one
  obsolete Chainlink fixture failure: its mock returned an address for the new
  optional integer phase read. The corrected fixture retains the static-feed
  fallback assertion and verifies both native queries. The corrected full required-command run then passed 2,292 tests with 17 skips
  and no OOM under 8 GiB/no swap. The preceding run passed 2,225 tests and failed 44 controlled quote
  fixtures that still mocked the previous SDK transport. All 128 tests in those
  two historical/address modules now pass at the native RPC boundary, preserving
  their exact fallback, packed-path, amount, and error-propagation assertions. The initial run failed on a full validation disk; the next passed 2,240
  tests with 17 skips but failed an outdated scaling fixture. Both failures are
  retained. The corrected fixture verifies streamed metadata, exact native
  quotes, ordering, and historical cache turnover.

A [real SDK-backed empty-cache Ethereum startup](pricing-repair/native-warmup-sigterm.json)
received SIGTERM during required Curve warmup. It aborted startup in 0.416
seconds, exited with startup-failure status 3, and never emitted readiness.

Only Curve initialization is required for readiness. Optional protocol warmups
run as owned background work after required initialization; SIGTERM cancels and
joins them. The latest [empty-cache Base check](pricing-repair/empty-base-startup-grouped.json)
became ready in 587.04 seconds and stopped on SIGTERM in 0.68 seconds, within
the existing startup and stop graces. The earlier passing check took 573.71 seconds. The earlier 633-second run failed that
grace and remains recorded. The successful process stopped normally on SIGTERM
without an OOM. Persisted-cache candidates stayed below approximately 1.1 GiB
during the measured quotes; this is candidate evidence, not production soak proof.

The Base reference feed aliases native USDC history to Ethereum's earlier token.
Validation now starts Base history at native USDC deployment: block 2,797,221,
timestamp 1,692,383,789. The previous block has no code. This avoids comparing
pre-chain reference dates while retaining Ethereum's depeg history.

## Candidate pricing evidence

The [final-source two-chain matrix](pricing-repair/candidate-matrix-native-calls.json)
completed 104 comparisons with zero API or pricing failures: 96 reference
comparisons passed, and eight successful API responses had no reference price.
Ethereum used its production web3-proxy and Base used its existing provider.
These were isolated candidate containers with copies of persisted production
caches, not the deployed application. Both historical USDC amount values below
and duplicate ordering in mixed batches passed exactly.

The earlier [independent-provider matrix](pricing-repair/candidate-matrix-before-shared-warmup.json)
failed on a cold real xPREMIA request at the 300-second deadline. Recovery did
not erase the failed result. Its trace showed background warmup and token
discovery competing on separate factory scan paths. Broad factory filters now
use the same shared owner as token filters; regression tests reproduce both V2
and V3's former duplicate scan paths and verify reuse, cancellation, and restart.

After that repair, a [fresh persisted-cache copy](pricing-repair/xpremia-cold-production-provider.json)
priced real xPREMIA through the production proxy in 247.675 seconds. A subsequent
current request took 10.694 seconds at a distinct head, so it is a new-block
measurement rather than a cached repeat. The 300-second request budget remains
unchanged. The host was recovering from an outage during this measurement.

The [independent backing calculation](pricing-repair/xpremia-backing.json)
matches xPREMIA's API price at block 19,000,000 and at a pinned current block,
using native PREMIA balances, supply, and both token decimal counts. The
[deployment checks](pricing-repair/xpremia-deployment-boundary.json) verify no
code at block 11,807,486 and zero backing and supply at deployment block
11,807,487; both API requests returned a definitive unavailable price.
plDAI and plUSDC current prices also passed through their restored underlyings.

The [native code-presence comparison](pricing-repair/code-presence-native.json)
checks the batched EXTCODESIZE helper against ordinary eth_getCode at historical
Base blocks, including before native USDC deployment. The helper is evaluated
only within eth_call at the exact canonical block hash. No deployment or
transaction is sent. Its source, reproducible compiler settings, and three
Foundry tests (including 256 fuzz cases) live in the fork's validation tools.

The [independent-provider benchmark](pricing-repair/candidate-benchmark-independent-provider.json)
retains first, changed-amount, mixed-batch, unseen-token, repeated, and distinct
new-block timings. Its Ethereum measurements use a backup node and cannot prove
production-proxy improvement. Base new-block quotes took approximately 14–16
seconds, versus the previous 104.871-second first current quote. These are
different cache phases; final production timings remain a delivery gate.

The historical pool inventories also match the existing pool-object iterator
exactly at the pinned quote blocks. [Ethereum](pricing-repair/historical-pool-discovery-ethereum.json)
retained 3,189 Uniswap V2, 242 SushiSwap, 14 ShibaSwap, and 1,825 V3 USDC pools.
[Base](pricing-repair/historical-pool-discovery-base.json) retained 1,031 Uniswap
V2, 57 SushiSwap, 633 Aerodrome V2, 2,200 Uniswap V3, and 49 Slipstream USDC pools. Their address-set digests
and differences are recorded; every difference set is empty.

Two [empty-cache Ethereum](pricing-repair/empty-ethereum-startup-before-provider-trace.json)
[startup attempts](pricing-repair/empty-ethereum-startup-traced-before-grouping.json)
failed the 600-second grace. A traced restart completed required initialization
in 98.77 seconds using the partially populated isolated cache, which is not an
empty-cache pass. The fresh trace showed two registry histories being scanned
separately. Their overlapping history now uses one bounded multiple-address
scan, then each registry consumes its own persisted events.

The [fresh grouped-registry startup](pricing-repair/empty-ethereum-startup-grouped.json)
passed in 534.95 seconds through the production web3-proxy. Actual SIGTERM after
readiness completed in 1.21 seconds with exit code 0 and no OOM. Six targeted
regressions cover coverage reuse, integration order, cancellation, and errors;
the relevant 47-test group and strict mypy passed. The [complete Curve inventory](pricing-repair/curve-inventory-parity.json)
also matched at the same canonical block: 2,564 LP mappings, two registries,
seven factories, and 1,416 coin entries, with an identical inventory digest.

Read-only probes after host recovery found a historical 10,000-block Curve
address-provider scan took 5.154 seconds through web3-proxy, 1.413 seconds on
Geth, and 0.334 seconds on Reth; all returned the same empty result. All three
reported the same fully synced head. No provider was changed.

The [empty-cache matrix](pricing-repair/empty-cache-matrix-before-registry-first.json)
then exposed historical USDT timeouts while Chainlink's full feed catalog was
loading. Its [completed report](pricing-repair/empty-cache-matrix-before-registry-first-complete.json)
also includes failures caused by deliberately stopping that obsolete candidate;
it is retained as a failed run. Quotes now query `getFeed` at the canonical hash
first. If no feed is active, `getCurrentPhaseId` distinguishes a removed feed
from an asset with no registry history, preserving static aliases. Event metadata
remains the fallback when phase data is unavailable. Fifteen new tests failed
before the repair; all 436 tests in the relevant group passed after repair,
including independent native feed comparisons, same-hash feed/value checks,
static aliases, removals, unavailable phase data, and timeout/cancellation propagation.
The final 17-case fixture audit also verifies recovery after transient errors.
Strict mypy covered 241 files and all ten compiled extension imports passed.
The [uncached historical USDT API replay](pricing-repair/chainlink-uncached-api-after.json)
returned the native historical value in 0.21 seconds. The [corrected copied-cache
matrix](pricing-repair/candidate-matrix-registry-first.json) again passed all 104
comparisons on both existing production providers. The [fully fresh startup and uncached replay](pricing-repair/empty-ethereum-startup-registry-first.json)
with this latest repair passed: readiness in 591.99 seconds within the 600-second
grace, the formerly failing USDT quote in 2.21 seconds with no cache hit, then
a clean SIGTERM shutdown in 0.94 seconds with no OOM. This check ran concurrently
with the copied-cache amount benchmark on the same production proxy.

The [pre-deployment public browser smoke](pricing-repair/browser-both-before-deployment.json)
passed Ethereum USDC/USDT/WETH and Base USDC/WETH using isolated Playwright Chromium
after the browser connector reported no connected browser. Permanent browser
coverage now verifies the matching chain/token HTTP response and its displayed
price, records JSON timings, and rejects API errors. [Controlled checks](pricing-repair/browser-validation-negative-checks.json)
rejected HTTP 502, wrong-chain, and wrong-token responses even after an earlier
successful quote. Post-deployment browser proof remains pending.

## Final-source amount benchmark

The [production-provider benchmark](pricing-repair/candidate-benchmark-production-provider.json)
passed all 24 requests after restarting the isolated candidates with the final
source. RAM was cold and their copied disk caches were already populated; this
is not an empty-cache production benchmark.

| Phase | Ethereum seconds | Base seconds |
| --- | ---: | ---: |
| Historical USDC amount, first after restart | 10.386 | 11.035 |
| Same request repeated | 0.049 | 0.056 |
| Changed amount | 0.086 | 0.676 |
| Mixed batch with duplicate token order | 0.073 | 0.101 |
| Previously unseen WETH amount at the historical block | 37.767 | 164.855 |
| Three distinct new blocks | 11.381 / 9.517 / 10.517 | 15.077 / 13.649 / 13.259 |
| Their repeats | 0.046 / 0.048 / 0.045 | 0.062 / 0.057 / 0.055 |

The [latest registry-first runtime benchmark](pricing-repair/candidate-benchmark-registry-first.json)
also passed all 24 requests after both candidates restarted. It ran concurrently
with a separate empty-cache Ethereum startup through the same proxy, so these
measurements include that additional validation traffic.

| Phase | Ethereum seconds | Base seconds |
| --- | ---: | ---: |
| Historical USDC amount, first after restart | 24.272 | 17.103 |
| Same request repeated | 0.057 | 0.084 |
| Changed amount | 0.265 | 0.767 |
| Mixed batch with duplicate token order | 0.091 | 0.092 |
| Previously unseen WETH amount at the historical block | 99.101 | 187.262 |
| Three distinct new blocks | 14.479 / 12.081 / 11.594 | 32.305 / 28.309 / 19.531 |
| Their repeats | 0.044 / 0.047 / 0.036 | 0.229 / 0.179 / 0.135 |

An [earlier production-provider benchmark](pricing-repair/candidate-benchmark-before-native-calls.json)
failed its first historical USDC amount at 300 seconds, despite the preceding
price matrix passing. A native call through the same proxy and pinned block
completed in 27 milliseconds; a separate fresh SDK process also completed
quickly. The trace implicated the shared SDK request path in the failed process,
rather than proving a proxy or persistent SDK latency problem. Amount-state
reads and V3/Slipstream quoter calls now use bounded native transport at the
same canonical hash. Tests verify exact packed path bytes, quantities, signed
Slipstream spacing, V1/V2 outputs, fees, and full-input-consumption proof.
The failed benchmark remains recorded and cannot count toward acceptance.

## Retained failed candidate checks

An early Base candidate exceeded its 8 GiB cap and exited with Docker OOM status.
Subsequent candidates exposed SDK retry delays, provider rate limits, expensive
per-pool code reads, and slow factory backfill. Their 300-second timeouts and
rate-limit failures remain failures even after later recovery. Native reserve
and balance batches, indexed immutable metadata, bounded code reads, and the
code-presence helper address those observed paths while preserving every eligible
pool, historical block ceilings, native quantities, fees, and quote ordering.
No failed candidate is included in a successful production soak.

The first attempted production-provider matrix was launched while its isolated
Base candidate was restarting; it failed the required-chain health gate before
pricing. The subsequent complete run above started after both candidates were
healthy. This startup failure is preserved separately from pricing results.

A [warm candidate repeat with strict amount assertions](pricing-repair/candidate-benchmark-exact-warm.json)
passed all 24 requests. Historical goldens require exact equality, and both
mixed-batch amount entries equal their corresponding individual requests. This
repeat reuses warmed process memory; the first-request timing tables above
remain the cold-process measurements.

The [complete native Python 3.12 run](pricing-repair/native-complete-312.json)
passed 2,292 tests, skipped 17, and imported all ten expected compiled modules.
Peak cgroup memory was 2.07 GiB with no swap or OOM. All 203 pricing/test source
files match the validated feature commit; strict typing covered 241 files.

## Before measurements

The earlier production verification measured historical USDC quotes at
`1000.000001` readable units: Ethereum block 19,000,000 = `0.9989039883929369`
and Base block 24,000,000 = `0.990993596876513`.
First current-block amount quotes took 31.984 seconds on Ethereum and 104.871
seconds on Base; another Ethereum block took 28.345 seconds. Repeats took
0.128/0.156 seconds. These are prior measurements, not evidence for this repair.

Read-only probes on ski-lambo-1 requested Uniswap V3 factory events starting at
block 25,000,000. Each target returned identical event counts (39 at 10,000 blocks;
2,138 at 200,000 blocks). Three samples per target:

| Target | 10,000-block seconds | 200,000-block seconds |
| --- | --- | --- |
| web3-proxy | 0.551, 0.224, 0.228 | 17.985, 13.037, 9.747 |
| Geth | 0.195, 0.149, 0.036 | 4.830, 3.709, 3.853 |
| Reth | 0.208, 0.198, 0.220 | 8.527, 10.052, 8.887 |

Production remains on web3-proxy for Ethereum and its existing Base provider.
SQLite backups were made through read-only connections into separate temporary
files for both chains; production cache volumes were retained.

ski-lambo-1 was unreachable over both LAN and Tailscale from 06:20 UTC on
October 2. It became reachable again with a new uptime around 15:56 UTC; the
system Docker web3-proxy was healthy when checked, and both public backend
health checks recovered. Candidate validation continued against an independent
node during the outage. Production providers were preserved.

## First repair deployment and uncovered failures

Fork [PR #47](https://github.com/SatoshiAndKin/ypricemagic/pull/47) merged to
`master` as `073c7ac801ca36128eb27efc64031851ab6f2101`, followed by server
[PR #158](https://github.com/SatoshiAndKin/ypricemagic-server/pull/158), merged as
`be640a5bc2f0e1db3ced13b29b0f77fb7a5b4de7`. All 13 fork checks and six server
checks passed. [Deployment run 37064574100](https://github.com/SatoshiAndKin/ypricemagic-server/actions/runs/37064574100)
succeeded; the deployment worker independently recorded success for request
`9049ee4d6bca44ee94342bf1ce421a13`.

[Deployment assertions](pricing-repair/production-first-deployment-assertions.json)
passed for all three images. Both backends installed the merged fork revision,
loaded compiled code, retained their original provider and cache volumes, and
have an 8 GiB limit with swap disabled. Container-to-ready times were 17.56 seconds
for Ethereum and 21.46 seconds for Base. Neither backend had an OOM or restart.

Production acceptance **failed**. The [public timing run](pricing-repair/production-first-deployment-benchmark.json)
passed 16 requests before Base WETH at block 24,000,000, amount `0.1`, returned
HTTP 504 after 300.07 seconds. The server enforced one deadline promptly, but the
underlying cold discovery remains a release failure. Historical USDC goldens and
mixed-batch ordering still matched exactly. Ethereum's first historical quote
was 8.53 seconds, first historical WETH 52.51 seconds, and three previously unseen
recent-block quotes 9.45, 7.34, and 7.18 seconds. These timings do not establish a
complete matrix or soak.

The separate [candidate turnover run](pricing-repair/candidate-turnover-failure.json)
also failed: Ethereum USDC at block 26,107,234, amount `1000.000001`, returned
HTTP 504 after 35.88 seconds. Both chains completed 2,200 distinct amounts and
retained exact post-eviction historical results; there were no OOMs or restarts.
Peak cgroup use was approximately 1.00 GiB for Ethereum and 4.58 GiB for Base.
This isolated run lasted 54.81 minutes and is not a production soak. Its failure
remains recorded independently of any later recovery.

A fresh copy of the untouched Base production SQLite backup reproduced the
WETH failure at 300.01 seconds. Profiling found expensive historical backfill
and many immutable Solidly stable-flag reads. Follow-up work carries the stable
flag from the factory event and retries one transient transport timeout at the
same canonical hash, inside the existing deadline. The initial repaired copied-cache
run returned the unchanged WETH price `1969.89808` in 291.30 seconds. This is
candidate evidence only; further repair and production proof remain pending.

## Remaining delivery gates

The latest [empty-cache Base WETH check](pricing-repair/base-empty-cache-weth-failure.json)
still failed at 300.004 seconds despite successful startup in 18.22 seconds.
This candidate used seven interpreted overlays from fork #48 over the original
merged image; it is not final production-image proof. It stopped normally without
an OOM. The profiler recorded more than 17,000 cache-range reads from the legacy
background Uniswap warmup while foreground amount discovery was waiting.

The server follow-up now warms the USDC anchor with compact metadata batches,
counting entries without constructing pool objects or starting legacy filters.
Three regressions fail on the prior server behavior, and the repaired server
passes 336 tests, strict typing, formatting, lint, and dependency checks.
The cold request is being repeated before accepting this repair.

[Infrastructure PR #77](https://github.com/SatoshiAndKin/dockerfiles/pull/77)
also corrects the proxy's explicit 128-block Geth log-history limit while leaving
the state-history limit at 128. Its regression tests, complete local validation,
native production-image configuration parser, and CI passed. The existing worker
is applying the merged configuration; runtime and cold Ethereum acceptance are
still pending. Ethereum continues using web3-proxy, and Base keeps its original
provider.

Validate and merge follow-up fork repairs, refresh the server lock against
`master`, validate and deploy through the existing pipeline, then run the complete
corrected historical/current matrix, public redirect and direct Tailscale/browser
smoke, timing comparisons, and at least 60 minutes of production soak with cache
turnover, memory, restart, Docker OOM, and kernel OOM checks. Acceptance requires
no unexpected pricing failures. The failed runs above cannot be erased by a
successful recovery or restart.
