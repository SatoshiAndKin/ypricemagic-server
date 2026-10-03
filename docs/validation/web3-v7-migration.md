# Web3 v7 immutable pricing stack

The server dependency is pinned to pricing revision
`f03904c8c79183703093bebc59ec6bf955e39e02`, built on fork master `073c7ac8`.
That revision uses dank-mids `fa4b454fb8d33c2f412709da4daca522cd4f7e47`, Brownie
`7e529be8dfc1afa7bda2d6660c8a11c59a653a6e` and evmspec
`f0df0d9d8e4e7a7000580054ce2c0b6b6193a14c`. The repaired ez-a-sync, cachebox
and aiosqlite pins and existing server security overrides are preserved.
The refreshed lock resolves Web3 7.16.0 exclusively.

The server implementation is unchanged: exact Decimal inputs, mixed batch order,
duplicate tokens, spot cache behavior, transport deadlines, error sanitization,
shutdown and existing cold-start mitigations retain their public contracts.
Tests receive isolated disk caches to prevent cached responses from another test
bypassing the behavior under test. Pytest flags and mypy targets are centralized
in pyproject.toml; workflow/hook invocations use the configured runners. Workflow
caches and path filters are retained, and immutable lock checks also run on PRs.

A fresh Linux ARM64 image built using the existing Dockerfile and locked sources.
All 333 server tests passed, including exact amounts, batching, cache/schema,
startup/shutdown and cancellation regressions. Strict mypy passed all 18 source
files; Ruff, formatting, actionlint and the immutable lock check passed. Application
coverage was 89%. Installed native modules include Dank's controller and vendored
aiolimiter, Brownie's caching middleware, evmspec._new, ez-a-sync, and the pricing
conversion/exception modules. A separate pricing source run covers every changed
runtime statement; compiled verification is independent.

The immutable Linux ARM64 image passed internal HTTP health, historical spot
prices, duplicate/order-preserving batches, single and mixed amount requests,
and spot-cache preservation on Ethereum (block 18,000,000) and Base (20,000,000).
Independent native SDK checks retained exact raw amounts 1,000,001 and 2,000,001
and canonical block hashes on both chains. The image uses its unchanged entrypoint
and Dockerfile; no pricing overlays or diagnostic startup hooks were used.

Validation-VM disk exhaustion interrupted the first run; only this migration's
obsolete containers, caches and builder artifacts were removed before repeating
acceptance. Base's first amount request reached the unchanged 300-second deadline
while its catalog loaded. Repeating the same request after catalog loading passed,
including exact amount and spot-cache assertions. This does not establish that
an empty-cache Base amount request always completes within 300 seconds.

The complete native pricing suite remains required. After the original archive
provider exhausted its monthly capacity, an independent archive run completed
2,310 passing cases and 17 skips with one batch/individual fOUSG price discrepancy
at block 21,578,484. Three complete token-list replays at that block and all ten
concurrent historical batch/individual tests passed unchanged. The full suite is
being repeated with targeted price-path tracing. This migration remains draft
pending that check. The archive profile uses a separate populated catalog snapshot,
an encrypted loopback connection, eight concurrent cases and a 1,000-call multicall
limit; it does not establish empty-cache startup performance. Deployment is separate.


The refreshed lock also pins cchecksum's owned-buffer repair at
`fff7e1fe87f4679ec96de1cebb1cdd8f5e94be44` in runtime overrides and isolated
build constraints. A fresh image with these exact sources passed all 333 server
cases under the debug allocator, strict mypy for 18 files, Ruff, formatting,
deptry and the immutable lock check. All eight Ethereum HTTP scenarios passed
through encrypted loopback archive access. Repeating Base startup against the
original provider hit its exhausted monthly quota; anonymous alternatives rejected
large log requests or denied access. The prior Base image checks remain historical
evidence and are not final acceptance of this refreshed image.

The latest full pricing repeat completed 2,310 passes and 17 skips with two exact
batch-equality failures in the yvCurve/IronBank lending market. A separate pricing
repair isolates its oracle from simulated interest accrual while retaining JSON-RPC
batching. Its controlled HTTP regression and three exact-block token-list replays
pass, as do 827 focused cases and strict mypy for 242 files. This server lock still
needs that final pricing revision and the completed full-suite acceptance. It is a
draft and has not been deployed.
