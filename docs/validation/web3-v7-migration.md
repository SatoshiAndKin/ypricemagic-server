# Web3 v7 immutable pricing stack

The lock pins pricing `8c8387ec15f4f8a119214df5971f10b79cfb6962`, retaining
pricing master `cb4a12376b807b1b9f27d9963f0c457edf02fda7`. It uses dank-mids
`90baeae436f4d359538b11988c13a86004e2e087`, Brownie
`7e529be8dfc1afa7bda2d6660c8a11c59a653a6e` and evmspec
`31c8540a14228ca49c77c19d565a6aaee3d0079f`. Runtime overrides and isolated
build constraints share cchecksum's owned-buffer revision
`fff7e1fe87f4679ec96de1cebb1cdd8f5e94be44`. Existing native dependency fixes
and security overrides are retained. The 149-package lock resolves Web3 7.16.0.

Pin eth-abi 5.2.30 and faster-eth-utils 5.3.28, the exact versions tested in the
native pricing image. Newer isolated source builds require a conflicting checksum
version. Matching the tested graph makes a fresh locked build reproducible.

Current server main `de6a683` is merged, including uncached-request priority,
readiness/deadline, routing and security repairs. The migration preserves public
APIs, exact Decimal inputs, mixed batch ordering, duplicate tokens, spot caching,
error sanitization, shutdown and existing cold-start mitigations. Test disk caches
are isolated so previous responses cannot bypass the behavior under test. Pytest
and mypy settings remain centralized; workflow caches/path filters are retained.

## Final image acceptance

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
results are not acceptance of this final image. No migration PR has been merged,
and deployment remains a separate step. Original draft branches are retained.
