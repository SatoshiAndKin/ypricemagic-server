# Changelog

## [0.6.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.5.1...v0.6.0) (2026-03-05)


### Features

* from→to quote endpoint, UI quote form, theme toggle, and UI polish ([#37](https://github.com/SatoshiAndKin/ypricemagic-server/issues/37)) ([c5439bb](https://github.com/SatoshiAndKin/ypricemagic-server/commit/c5439bba1eb4e7f6861883cc0a5ed91b041b64ab))
* Python 3.13, price validator, UI polish, token display, and infra split ([#41](https://github.com/SatoshiAndKin/ypricemagic-server/issues/41)) ([92407d5](https://github.com/SatoshiAndKin/ypricemagic-server/commit/92407d58e5bb7f3cf6067b8ab7eb9d5cb4a6ad7c))
* token autocomplete, tokenlist management, and zero-downtime deploy ([#35](https://github.com/SatoshiAndKin/ypricemagic-server/issues/35)) ([4f726fb](https://github.com/SatoshiAndKin/ypricemagic-server/commit/4f726fbcad0046ff9be4c131edb05c82a7a70549))
* update ypricemagic and expose trade path in API responses ([#38](https://github.com/SatoshiAndKin/ypricemagic-server/issues/38)) ([5377285](https://github.com/SatoshiAndKin/ypricemagic-server/commit/53772856edd1bb6c185a994c7b7fd76362d7d296))


### Bug Fixes

* cap dank_mids EXTRA_QUEUED_CALLS on macOS to avoid SEM_VALUE_MAX crash ([#40](https://github.com/SatoshiAndKin/ypricemagic-server/issues/40)) ([4f032cc](https://github.com/SatoshiAndKin/ypricemagic-server/commit/4f032cc5b5958f62915bdf0173a9f877a20e9bea))
* use env_file in docker-stack.yml for swarm compatibility ([#42](https://github.com/SatoshiAndKin/ypricemagic-server/issues/42)) ([f6430b6](https://github.com/SatoshiAndKin/ypricemagic-server/commit/f6430b627fa82d2137322e7fa6483623903e80ff))

## [0.5.1](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.5.0...v0.5.1) (2026-03-03)


### Bug Fixes

* add ready_for_review trigger and skip lockfile check on push-to-main ([#29](https://github.com/SatoshiAndKin/ypricemagic-server/issues/29)) ([6240fc4](https://github.com/SatoshiAndKin/ypricemagic-server/commit/6240fc4470a3d0d329a0cda02855745323b2dd48))
* consistent button sizing and better bucket classification UX ([#32](https://github.com/SatoshiAndKin/ypricemagic-server/issues/32)) ([c3b0f36](https://github.com/SatoshiAndKin/ypricemagic-server/commit/c3b0f363f5458401d3c6ac3002bd58a2fb79c513))
* make date picker clearable and include details in error messages ([#31](https://github.com/SatoshiAndKin/ypricemagic-server/issues/31)) ([03a33c6](https://github.com/SatoshiAndKin/ypricemagic-server/commit/03a33c65c40b1dd1c6fbfa1c432df16538d1a080))
* remove skip-cache/silent from UI and improve form defaults ([#33](https://github.com/SatoshiAndKin/ypricemagic-server/issues/33)) ([15b8cfe](https://github.com/SatoshiAndKin/ypricemagic-server/commit/15b8cfe82f26d961fa6bc4fa345b64384646294f))
* update ypricemagic to fix Chainlink feed resolution and reduce path explosion ([#34](https://github.com/SatoshiAndKin/ypricemagic-server/issues/34)) ([6e8adee](https://github.com/SatoshiAndKin/ypricemagic-server/commit/6e8adeee574066396aefa1da9bdacb1d99970c11))

## [0.5.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.4.1...v0.5.0) (2026-03-03)


### Features

* batch form per-token rows with inline amounts and chain mismatch warning ([#28](https://github.com/SatoshiAndKin/ypricemagic-server/issues/28)) ([21a945d](https://github.com/SatoshiAndKin/ypricemagic-server/commit/21a945dcfaaf356e2ff34c79c58d1e8eb40da95c))
* unify block/timestamp into single field with date picker ([#27](https://github.com/SatoshiAndKin/ypricemagic-server/issues/27)) ([4bd6803](https://github.com/SatoshiAndKin/ypricemagic-server/commit/4bd6803078cc72211fe37ccb959db7f6e69d5150))


### Documentation

* add git workflow rules to AGENTS.md ([#25](https://github.com/SatoshiAndKin/ypricemagic-server/issues/25)) ([be4a693](https://github.com/SatoshiAndKin/ypricemagic-server/commit/be4a693adfcc6e91c0aad9e3be3afb8f21f72438))

## [0.4.1](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.4.0...v0.4.1) (2026-03-02)


### Bug Fixes

* update uv.lock in release-please PRs to keep lockfile in sync ([#22](https://github.com/SatoshiAndKin/ypricemagic-server/issues/22)) ([746e4f2](https://github.com/SatoshiAndKin/ypricemagic-server/commit/746e4f2f94199c5a0ffc4b3a179cc68373adca87))

## [0.4.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.3.0...v0.4.0) (2026-03-02)


### Features

* ypricemagic upgrade - new endpoints, UI, and docs ([80049c1](https://github.com/SatoshiAndKin/ypricemagic-server/commit/80049c147cdf4a72736e1e0481662148a7eadeae))


### Bug Fixes

* add init: true to container services for proper SIGTERM handling ([#20](https://github.com/SatoshiAndKin/ypricemagic-server/issues/20)) ([21ceb03](https://github.com/SatoshiAndKin/ypricemagic-server/commit/21ceb0385b93b13b30f6d1dfe90a9171efdbfb18))
* move setuptools&lt;82 to main dependencies to fix container pkg_resources error ([#17](https://github.com/SatoshiAndKin/ypricemagic-server/issues/17)) ([49323b2](https://github.com/SatoshiAndKin/ypricemagic-server/commit/49323b296e31beeb7a2b6f5fe314e31929916daa))
* stop redacting token addresses in logs ([#19](https://github.com/SatoshiAndKin/ypricemagic-server/issues/19)) ([bb05684](https://github.com/SatoshiAndKin/ypricemagic-server/commit/bb0568443420dbd3425cde8a6101bc9f381b8006))

## [0.3.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.2.0...v0.3.0) (2026-02-27)


### Features

* add amount param for price impact, switch ypricemagic to git source ([#15](https://github.com/SatoshiAndKin/ypricemagic-server/issues/15)) ([0a44783](https://github.com/SatoshiAndKin/ypricemagic-server/commit/0a447836ceb1843e4dfabb1fb17c7afe5118b1d9))


### Bug Fixes

* make nginx resilient to individual chain backends being down ([#13](https://github.com/SatoshiAndKin/ypricemagic-server/issues/13)) ([e40385a](https://github.com/SatoshiAndKin/ypricemagic-server/commit/e40385a5d3e3123d6ce630d5104abe3097c6f357))
* replace nginx variable-based routing with path-based chain routing ([#16](https://github.com/SatoshiAndKin/ypricemagic-server/issues/16)) ([c2b99a5](https://github.com/SatoshiAndKin/ypricemagic-server/commit/c2b99a509f6888c608ee8e1f3663965f6c987250))

## [0.2.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.1.1...v0.2.0) (2026-02-27)


### Features

* remove Polygon chain support ([#11](https://github.com/SatoshiAndKin/ypricemagic-server/issues/11)) ([347b140](https://github.com/SatoshiAndKin/ypricemagic-server/commit/347b1403e5959f1ddb753b2c0c0d9c67c929d11d))

## [0.1.1](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.1.0...v0.1.1) (2026-02-25)


### Bug Fixes

* inject geth_poa_middleware for Polygon PoA blocks ([eb6202a](https://github.com/SatoshiAndKin/ypricemagic-server/commit/eb6202a1481a9894d9306b05b9af22a7de10f620))

## 0.1.0 (2026-02-25)


### Bug Fixes

* all CI checks and pre-commit hooks passing ([420fdb3](https://github.com/SatoshiAndKin/ypricemagic-server/commit/420fdb3c06b1db4f6baee80ed69631546e747156))
* remove unused noqa directive and print in export_openapi.py ([3abea9f](https://github.com/SatoshiAndKin/ypricemagic-server/commit/3abea9f0c444687e5a73569d0fb06ef6f0dcea77))
* resolve all 28 mypy errors ([83e6b76](https://github.com/SatoshiAndKin/ypricemagic-server/commit/83e6b76fa0d5ba830985fd94e322c323d2e78505))
