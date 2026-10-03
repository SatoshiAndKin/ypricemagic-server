# Web3 v7 immutable pricing stack

The lock pins pricing `8ef2e54bf23e74573555c8feb6120fd6c3825925`, retaining merged
pricing master `9fdfeb101751a1d82eb41dccb87c8c06fbac9e75`. It uses merged dank-mids
`33d64a962a2ff2a60f4ddb0d1d17e6b0fbbd89c0`, Brownie
`7e529be8dfc1afa7bda2d6660c8a11c59a653a6e` and evmspec
`31c8540a14228ca49c77c19d565a6aaee3d0079f`. Runtime overrides and isolated
build constraints share cchecksum's owned-buffer revision
`fff7e1fe87f4679ec96de1cebb1cdd8f5e94be44`. Existing native dependency fixes
and security overrides are retained. The 149-package lock resolves Web3 7.16.0.

Pin eth-abi 5.2.30 and faster-eth-utils 5.3.28, the exact versions tested in the
native pricing image. Newer isolated source builds require a conflicting checksum
version. Matching the tested graph makes a fresh locked build reproducible.

Current server main `40d400f` is retained, including the merged Base production
pause, uncached-request priority,
readiness/deadline, routing and security repairs. The migration preserves public
APIs, exact Decimal inputs, mixed batch ordering, duplicate tokens, spot caching,
error sanitization, shutdown and existing cold-start mitigations. Test disk caches
are isolated so previous responses cannot bypass the behavior under test. Pytest
and mypy settings remain centralized; workflow caches/path filters are retained.

## Original migration image acceptance

A fresh Linux ARM64 image, `yprice-server:web3-v7-query-safe`, was built from the
existing Dockerfile and locked sources. It runs the unchanged application entrypoint
without pricing overlays or diagnostic startup hooks.

- **346 tests and four subtests passed** under the debug allocator.
- Strict mypy passed **18 source files**; Ruff, formatting, deptry and the immutable
  lock check passed. All hosted server checks passed, including backend image build.
- Native imports include Dank's controller and vendored aiolimiter, Brownie's caching
  middleware, evmspec._new, ez-a-sync and all ten declared pricing extensions.
- All **eight real Ethereum HTTP scenarios** passed: health, historical USDC/WETH,
  cached reads, ordered duplicate batches, single/mixed amounts and preservation
  of the spot cache after amount quotes, at block 18,000,000.
- Separate native SDK calls preserve raw USDC amounts **1,000,001** and **2,000,001**
  with canonical block hash
  `0x95b198e154acbfc64109dfd22d8224fe927fd8dfdedfae01587674482ba4baf3`.

The freshly compiled pricing suite passed **2,664 tests with 17 skips**. Its separate
source profile covers **40/40 changed runtime statements (100%)**, independently of
compiled verification. Brownie's native memory/explorer regressions passed all
77 cases, and the SDK archive suite passed all 33. Fresh evmspec builds pass 365
cases with the same two pre-existing trace-enum failures as the original schema
revision; those unrelated failures are documented in its build repair PR.

Archive checks use a populated catalog snapshot and do not establish empty-cache
startup performance. Final Base verification is explicitly deferred at the user's
request following the original provider's exhausted monthly quota. Earlier Base
results are not acceptance of this final image. The original SDK, pricing and server migrations have been merged. Deployment of
this dependency follow-up remains a separate step. Original draft branches are
retained.

## Merged SDK follow-up acceptance

The refreshed 149-package lock changes only the pricing and SDK revisions. The
actual Dockerfile builds `yprice-server:merged-dank-33d64a9` against pricing
`8ef2e54bf23e74573555c8feb6120fd6c3825925` and merged SDK
`33d64a962a2ff2a60f4ddb0d1d17e6b0fbbd89c0`. Its configured suite passes
**346 tests plus four subtests**, with clean typing (18 files), Ruff, formatting
(26 files), dependency and offline lock checks. The unchanged application
entrypoint becomes ready against the private Ethereum archive endpoint.

All **eight real HTTP scenarios** pass with a fresh price cache: health, historical
USDC/WETH, cached reads, ordered duplicate batches, single/mixed amounts and spot
cache preservation. Amount quotes continue using actual sale estimates; the USDC
spot policy stays separate. Native calls preserve raw amounts **1,000,001** and
**2,000,001** and the exact canonical block-18,000,000 hash shown above. Compiled
imports verify all ten pricing modules and the SDK/controller/aiolimiter, Brownie,
evmspec and ez-a-sync; direct-URL metadata verifies the immutable source pins.

Pricing's full freshly compiled suite passes **2,664 tests with 17 skips**, strict
mypy passes **246 files**, and the SDK's **11 controlled hash-header error/recovery
cases** pass through the installed native controller. Archive checks use private
catalog and ABI snapshots under the debug allocator, with 8 GiB/no swap/4 CPUs/512
processes; they do not establish empty-cache startup performance. Server main's
merged Base production pause is retained. Base verification remains deferred.
