# Changelog

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
