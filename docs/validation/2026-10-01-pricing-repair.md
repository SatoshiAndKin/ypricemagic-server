# Pricing, startup, and validation repair

Updated October 2, 2026. The repair is in progress. Production acceptance has not been claimed. Production
continues to run server `2cf834e5e63303a0d75431a22e000c14f45024e6` and pricing fork
`69dda57e63039a359420a4177ca688c378e9be9a` until both linked repairs are validated.

## Reproduced failures and provenance

Five routing/cache/startup regression tests failed against the deployed server:
required warmup cancellation returned normally; ambiguous persisted errors were
reused; transient failures entered the 404 cache; timeouts were attempted twice;
and slow cancellation delayed the HTTP timeout response. These predate PRs
152/156/157: signal handling was introduced in PRs 137/139, error caching in PR
124, and the lookup timeout in PR 58.

Six pricing-fork regressions failed against the deployed revision: broader
factory coverage was ignored for both token topic positions and alternatives;
disjoint scans falsely claimed the gap; and plDAI/plUSDC mappings were absent.
Token discovery's repeated scans were exposed by fork PR 46. The cache coverage
and missing mapping behavior also exist in its parent, the PR 43 merge.
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

- Server: 327 tests passed; 89% coverage. Ruff, format, strict mypy, deptry passed.
- Real process SIGTERM during warmup and after readiness passed; cancelled startup
  did not log readiness, and both processes stopped within five seconds.
- Saturation test fills exactly two active slots and 32 queued requests; additional
  work returns 503 while cached price and health requests return 200.
- Frontend: Svelte check, 89 tests, and production build passed.
- Fork: the final-source targeted native Python 3.12 run passed 404 tests,
  strict mypy covered all 240 Python files, and ten extension imports were
  confirmed to resolve to compiled `.so` modules. Two native xPREMIA
  deployment-boundary checks also passed. Black/isort checks cover the full trees.
- A full native run passed 2,259 tests with 17 skips and no OOM. Its source
  predates the final native-call transport and shared broad factory repairs.
  The final-source full suite is running with 8 GiB/no swap and remains a merge
  gate. The initial run failed on a full validation disk; the next passed 2,240
  tests with 17 skips but failed an outdated scaling fixture. Both failures are
  retained. The corrected fixture verifies streamed metadata, exact native
  quotes, ordering, and historical cache turnover.

A [real SDK-backed empty-cache Ethereum startup](pricing-repair/native-warmup-sigterm.json)
received SIGTERM during required Curve warmup. It aborted startup in 0.416
seconds, exited with startup-failure status 3, and never emitted readiness.

Only Curve initialization is required for readiness. Optional protocol warmups
run as owned background work after required initialization; SIGTERM cancels and
joins them. In the empty-cache Base check, readiness took 573.71 seconds, within
the existing 600-second health grace. The earlier 633-second run failed that
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
node during the outage. No provider switch or task deployment was performed.

## Remaining delivery gates

Fork repair [PR #47](https://github.com/SatoshiAndKin/ypricemagic/pull/47) is a
draft. Remaining gates: final fork validation, production image builds, linked
server feature-branch PR, fork
merge then server lock refresh against `master`, pipeline deployment with image
and installed dependency revision checks, corrected historical/current matrix,
public redirect and browser smoke, and a 60-minute production soak with cache
turnover, memory, restart, Docker OOM, and kernel OOM checks.
