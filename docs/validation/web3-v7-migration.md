# Web3 v7 immutable pricing stack

The server dependency is pinned to pricing revision
`03acd2b9238def0549e7eaea371bd8d45c5e3377`, built on fork master `073c7ac8`.
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

Live Ethereum/Base startup, price, batch, amount and cache scenarios and the
complete native pricing suite remain acceptance requirements. This migration
stays draft until those checks pass. Deployment is separate.
