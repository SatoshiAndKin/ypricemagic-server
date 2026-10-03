# Web3 v7 immutable pricing stack

The server dependency is pinned to pricing revision
`a9f07c085c4d9d3bc152e1a6d0e9a88a4d7f5aa5`, built on fork master `073c7ac8`.
That revision uses dank-mids `2a5a4d21fc8aa1d12a9146043871ade23084323c`, Brownie
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

The complete native pricing suite is running after the Web3 session-lock repair.
This migration remains draft until that final check passes. Deployment is separate.
