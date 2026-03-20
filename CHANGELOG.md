# Changelog

## [0.13.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.12.0...v0.13.0) (2026-03-20)


### Features

* fetch real token metadata for unknown tokens + startup UX improvements ([#136](https://github.com/SatoshiAndKin/ypricemagic-server/issues/136)) ([2f485dd](https://github.com/SatoshiAndKin/ypricemagic-server/commit/2f485ddf952d5798fefb0d167117f41e1bdbaa08))
* use ypricemagic pool-index branch with Curve perf improvements ([#126](https://github.com/SatoshiAndKin/ypricemagic-server/issues/126)) ([08c50e7](https://github.com/SatoshiAndKin/ypricemagic-server/commit/08c50e7c3b3cb0f4606c2865d8e56f41f5edfb68))


### Bug Fixes

* concurrent uniswap prewarm and restore uvicorn signal handlers ([#139](https://github.com/SatoshiAndKin/ypricemagic-server/issues/139)) ([4efbc55](https://github.com/SatoshiAndKin/ypricemagic-server/commit/4efbc5594dffb123bcdcc2bc4b2424576c636bd1))
* graceful shutdown during startup prewarm ([#137](https://github.com/SatoshiAndKin/ypricemagic-server/issues/137)) ([c2bb682](https://github.com/SatoshiAndKin/ypricemagic-server/commit/c2bb68287c21c525d82b6eb1492aa00758d9c300))
* simplify prewarm cancellation — gather propagates cancel to children ([#138](https://github.com/SatoshiAndKin/ypricemagic-server/issues/138)) ([ac938dc](https://github.com/SatoshiAndKin/ypricemagic-server/commit/ac938dccd88136418b43a36782bccb4bbb44de11))

## [0.12.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.11.0...v0.12.0) (2026-03-16)


### Features

* add per-token lock and metadata to check_bucket ([#122](https://github.com/SatoshiAndKin/ypricemagic-server/issues/122)) ([193b50e](https://github.com/SatoshiAndKin/ypricemagic-server/commit/193b50ecd7d406df1fe5c9529e46e07f2e9264ee))
* auto-submit Get Price on page load ([#120](https://github.com/SatoshiAndKin/ypricemagic-server/issues/120)) ([9004582](https://github.com/SatoshiAndKin/ypricemagic-server/commit/90045820abb496436b0db7a2e6c0b455039590e8))
* show unit price and total output when amount is specified ([#121](https://github.com/SatoshiAndKin/ypricemagic-server/issues/121)) ([1099852](https://github.com/SatoshiAndKin/ypricemagic-server/commit/1099852c59002f5fbfb4b62b1391a40eebb749a8))
* use ypricemagic pool-index branch (PR [#16](https://github.com/SatoshiAndKin/ypricemagic-server/issues/16)) ([#125](https://github.com/SatoshiAndKin/ypricemagic-server/issues/125)) ([edabbce](https://github.com/SatoshiAndKin/ypricemagic-server/commit/edabbce242850c4a81fdb61302f72e961b14f7de))


### Bug Fixes

* restore result box details (timestamp, age, trade path) and cancel fetch on token change ([#118](https://github.com/SatoshiAndKin/ypricemagic-server/issues/118)) ([3dfdd08](https://github.com/SatoshiAndKin/ypricemagic-server/commit/3dfdd082005a96ae61a8fe251ff2b3b77a61f2df))

## [0.11.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.10.0...v0.11.0) (2026-03-14)


### Features

* add deploy webhook trigger to CD workflow ([#110](https://github.com/SatoshiAndKin/ypricemagic-server/issues/110)) ([cad6900](https://github.com/SatoshiAndKin/ypricemagic-server/commit/cad6900f96afa0ed0f248ca926c3b8bc531f1a5e))
* graceful cache shutdown, raise file descriptor ulimits, bump ypricemagic ([#102](https://github.com/SatoshiAndKin/ypricemagic-server/issues/102)) ([96cbc53](https://github.com/SatoshiAndKin/ypricemagic-server/commit/96cbc5397cab80bb4a88f574930b83e2d2e8ce46))
* shield price fetches from client disconnect cancellation ([#112](https://github.com/SatoshiAndKin/ypricemagic-server/issues/112)) ([85243d0](https://github.com/SatoshiAndKin/ypricemagic-server/commit/85243d05374370f3512a51f022c9f941452c408b))


### Bug Fixes

* bump ypricemagic to fix stablecoin hang, add debug logging ([#115](https://github.com/SatoshiAndKin/ypricemagic-server/issues/115)) ([9f91c37](https://github.com/SatoshiAndKin/ypricemagic-server/commit/9f91c371f3851a1bc31f320ea7a4f3072a02b8bb))
* increase price lookup timeout from 30s to 300s ([#109](https://github.com/SatoshiAndKin/ypricemagic-server/issues/109)) ([f7f03fb](https://github.com/SatoshiAndKin/ypricemagic-server/commit/f7f03fb2dc011c0b314e7b56637b6ab449ded90a))
* inject geth_poa_middleware for bsc, polygon, and fantom ([#104](https://github.com/SatoshiAndKin/ypricemagic-server/issues/104)) ([2383e52](https://github.com/SatoshiAndKin/ypricemagic-server/commit/2383e52e331712eeeba4f35f7e0c287be7b24386))
* remove duplicate geth_poa_middleware and pin setuptools&lt;81 ([#105](https://github.com/SatoshiAndKin/ypricemagic-server/issues/105)) ([645963a](https://github.com/SatoshiAndKin/ypricemagic-server/commit/645963ac438c8b0ea6154b77c5c47ca2c49f2a87))
* remove geth_poa_middleware injection, tighten setuptools to &lt;81 ([#106](https://github.com/SatoshiAndKin/ypricemagic-server/issues/106)) ([8f4139b](https://github.com/SatoshiAndKin/ypricemagic-server/commit/8f4139bc69d0bc038f0ac012786d582d53565c89))
* use correct API field names in frontend price display ([#116](https://github.com/SatoshiAndKin/ypricemagic-server/issues/116)) ([f048133](https://github.com/SatoshiAndKin/ypricemagic-server/commit/f048133ef5aad228957a6eaf8e25971f566e62d4))

## [0.10.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.9.0...v0.10.0) (2026-03-12)


### Features

* add bsc, polygon, fantom to network setup and OpenAPI servers ([#100](https://github.com/SatoshiAndKin/ypricemagic-server/issues/100)) ([d0910f0](https://github.com/SatoshiAndKin/ypricemagic-server/commit/d0910f0ab311f6234c52e5ecf275375ca2c9c98c))

## [0.9.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.8.2...v0.9.0) (2026-03-12)


### Features

* add bsc, polygon, and fantom to prod docker compose ([#99](https://github.com/SatoshiAndKin/ypricemagic-server/issues/99)) ([adb6851](https://github.com/SatoshiAndKin/ypricemagic-server/commit/adb6851f56c2ee40e02dd892d65c09092b09e74d))


### Bug Fixes

* install health log filter inside lifespan, not at import time ([#96](https://github.com/SatoshiAndKin/ypricemagic-server/issues/96)) ([ed6eaf5](https://github.com/SatoshiAndKin/ypricemagic-server/commit/ed6eaf5e965c8ae5c5848682d7f6ed64ce08c1c8))
* persist USD selection across refresh, add all chains to OpenAPI servers ([#97](https://github.com/SatoshiAndKin/ypricemagic-server/issues/97)) ([a5251cb](https://github.com/SatoshiAndKin/ypricemagic-server/commit/a5251cba0f7e57853147124561074ffff15a79ad))

## [0.8.2](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.8.1...v0.8.2) (2026-03-12)


### Bug Fixes

* shorten page title to just 'ypricemagic' ([#90](https://github.com/SatoshiAndKin/ypricemagic-server/issues/90)) ([1ae768a](https://github.com/SatoshiAndKin/ypricemagic-server/commit/1ae768ab1b05d2bdf914fd38fc54e60f466198fa))
* unify /price response to always use quote-mode envelope ([#92](https://github.com/SatoshiAndKin/ypricemagic-server/issues/92)) ([84362fb](https://github.com/SatoshiAndKin/ypricemagic-server/commit/84362fb369e10d71b1381d88419b0a0014e4905b))

## [0.8.1](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.8.0...v0.8.1) (2026-03-11)


### Bug Fixes

* use GitHub App token for release-please to trigger CI ([#88](https://github.com/SatoshiAndKin/ypricemagic-server/issues/88)) ([b991aa0](https://github.com/SatoshiAndKin/ypricemagic-server/commit/b991aa0c4b4f2c16f295fe0986beee8a150b0a45))

## [0.8.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.7.0...v0.8.0) (2026-03-11)


### Features

* update ypricemagic and add health indicator ([#85](https://github.com/SatoshiAndKin/ypricemagic-server/issues/85)) ([b7db497](https://github.com/SatoshiAndKin/ypricemagic-server/commit/b7db497a7720ea3aa0a70f89dca184db1d0f728a))


### Bug Fixes

* frontend polish round 2 ([#84](https://github.com/SatoshiAndKin/ypricemagic-server/issues/84)) ([7b6294d](https://github.com/SatoshiAndKin/ypricemagic-server/commit/7b6294d77f128b38e239584eb2385d6b3ec02309))
* handle null pool in trade path rendering ([#86](https://github.com/SatoshiAndKin/ypricemagic-server/issues/86)) ([6239bb6](https://github.com/SatoshiAndKin/ypricemagic-server/commit/6239bb673eef0d475c522e67c3824dbf393c1d15))
* persist all cache volumes (solcx, vvm, ypricemagic, app/cache) ([#87](https://github.com/SatoshiAndKin/ypricemagic-server/issues/87)) ([0a875f2](https://github.com/SatoshiAndKin/ypricemagic-server/commit/0a875f2d0c3ef3b7392bdcd6a354b26316804487))
* show actual trade path in quote route display ([#82](https://github.com/SatoshiAndKin/ypricemagic-server/issues/82)) ([1ea86ca](https://github.com/SatoshiAndKin/ypricemagic-server/commit/1ea86ca19878f7be6c40ca7084cd932cd527acaa))
* UI polish and documentation fixes ([#83](https://github.com/SatoshiAndKin/ypricemagic-server/issues/83)) ([ea4d041](https://github.com/SatoshiAndKin/ypricemagic-server/commit/ea4d041303062611aa8c1531cdbc506c340e6d22))
* unify header button sizes for consistent layout ([#79](https://github.com/SatoshiAndKin/ypricemagic-server/issues/79)) ([9ce74fe](https://github.com/SatoshiAndKin/ypricemagic-server/commit/9ce74fe5bb625dc0d93599e8432b01a746def923))
* use pull_request closed as sole main-branch CD trigger ([#81](https://github.com/SatoshiAndKin/ypricemagic-server/issues/81)) ([ed8381d](https://github.com/SatoshiAndKin/ypricemagic-server/commit/ed8381d5afcbd66f9526078d031e847ed8f10420))

## [0.7.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.6.0...v0.7.0) (2026-03-10)


### Features

* add Sentry error tracking to backend and frontend ([#67](https://github.com/SatoshiAndKin/ypricemagic-server/issues/67)) ([5544f16](https://github.com/SatoshiAndKin/ypricemagic-server/commit/5544f16f2e89b24a983ebf0ea7a2a7ea06e85263))
* default /price endpoint to USDC quote mode per chain ([#75](https://github.com/SatoshiAndKin/ypricemagic-server/issues/75)) ([a7698a1](https://github.com/SatoshiAndKin/ypricemagic-server/commit/a7698a15a502284aa435805973af7624b5054f81))
* frontend UX improvements and dependency updates ([#76](https://github.com/SatoshiAndKin/ypricemagic-server/issues/76)) ([8b583c7](https://github.com/SatoshiAndKin/ypricemagic-server/commit/8b583c73bb21dd14d4fa5002c6058d7682e0d2ef))
* streamline quote form layout and move docs to header ([#77](https://github.com/SatoshiAndKin/ypricemagic-server/issues/77)) ([d6f5ef0](https://github.com/SatoshiAndKin/ypricemagic-server/commit/d6f5ef05df4be2f0c70d8bffeede2dafc4b1bb21))


### Bug Fixes

* chain docs routing and upgrade deps (pytest 6→9) ([#60](https://github.com/SatoshiAndKin/ypricemagic-server/issues/60)) ([bada814](https://github.com/SatoshiAndKin/ypricemagic-server/commit/bada8147204a35a90198d07abd41bb303f69f324))
* defer sentry init until after dank_mids loads ([#69](https://github.com/SatoshiAndKin/ypricemagic-server/issues/69)) ([b189732](https://github.com/SatoshiAndKin/ypricemagic-server/commit/b18973223dc4c9e0f2ad0c601d9b9b27e56f5666))
* init tokenlist on mount, route quotes to /price, remove reset button ([#66](https://github.com/SatoshiAndKin/ypricemagic-server/issues/66)) ([ebb5371](https://github.com/SatoshiAndKin/ypricemagic-server/commit/ebb5371a6359bf5615cf8caec4484eb445986cd5))
* pin dank-mids to 4.20.202 to fix stats.logger AttributeError ([#70](https://github.com/SatoshiAndKin/ypricemagic-server/issues/70)) ([30661eb](https://github.com/SatoshiAndKin/ypricemagic-server/commit/30661eb29a4685a238d9197010e2e6a44134a97e))
* pin sentry-sdk&lt;3 (dank_mids needs set_measurement) ([#72](https://github.com/SatoshiAndKin/ypricemagic-server/issues/72)) ([b45ac73](https://github.com/SatoshiAndKin/ypricemagic-server/commit/b45ac732372d8713b834e42328ba7721f0926f22))
* prefix traefik router names with ypm- to avoid conflicts ([#71](https://github.com/SatoshiAndKin/ypricemagic-server/issues/71)) ([24f64d6](https://github.com/SatoshiAndKin/ypricemagic-server/commit/24f64d6d4bf97eb36a169da95f75f92430b8b27a))
* remove tokenlist proxy (SSRF surface), add server.py to coverage ([#68](https://github.com/SatoshiAndKin/ypricemagic-server/issues/68)) ([be7890c](https://github.com/SatoshiAndKin/ypricemagic-server/commit/be7890c6939e892cbda283568a42494775c991f8))
* rename network key to traefik-proxy, standardize DOMAIN env var ([#73](https://github.com/SatoshiAndKin/ypricemagic-server/issues/73)) ([5391c1b](https://github.com/SatoshiAndKin/ypricemagic-server/commit/5391c1be79f6b6f7a3134a5736b76cfab15816da))
* scrub RPC URLs and API keys from error responses ([#64](https://github.com/SatoshiAndKin/ypricemagic-server/issues/64)) ([21c2dfc](https://github.com/SatoshiAndKin/ypricemagic-server/commit/21c2dfc427fefef69ff2a92c55caed5bb4e903c3))
* switch validate_prices to DefiLlama with diskcache and consolidate API ([#58](https://github.com/SatoshiAndKin/ypricemagic-server/issues/58)) ([f528a6e](https://github.com/SatoshiAndKin/ypricemagic-server/commit/f528a6eae0eac18d6701f38b3717c18041b07582))
* trigger CI on release-please branch pushes ([#78](https://github.com/SatoshiAndKin/ypricemagic-server/issues/78)) ([33bc1ad](https://github.com/SatoshiAndKin/ypricemagic-server/commit/33bc1ad1452d9d1481a9d9568b4c9bf27be5b8e2))


### Documentation

* fix stale references in README/AGENTS + fix CI for docs-only PRs ([#65](https://github.com/SatoshiAndKin/ypricemagic-server/issues/65)) ([35c66c1](https://github.com/SatoshiAndKin/ypricemagic-server/commit/35c66c142afe9cb7a19dab078a225cd471e79064))

## [0.6.0](https://github.com/SatoshiAndKin/ypricemagic-server/compare/v0.5.1...v0.6.0) (2026-03-09)


### Features

* enable Traefik dashboard and relax image tag to v3 ([#49](https://github.com/SatoshiAndKin/ypricemagic-server/issues/49)) ([754329d](https://github.com/SatoshiAndKin/ypricemagic-server/commit/754329d3b7bf4434d1a740653dcb63358b6a42d0))
* enable Traefik dashboard API for debugging ([#50](https://github.com/SatoshiAndKin/ypricemagic-server/issues/50)) ([39c3120](https://github.com/SatoshiAndKin/ypricemagic-server/commit/39c312018570ad1d4986469441e007e53567f06f))
* from→to quote endpoint, UI quote form, theme toggle, and UI polish ([#37](https://github.com/SatoshiAndKin/ypricemagic-server/issues/37)) ([c5439bb](https://github.com/SatoshiAndKin/ypricemagic-server/commit/c5439bba1eb4e7f6861883cc0a5ed91b041b64ab))
* Python 3.13, price validator, UI polish, token display, and infra split ([#41](https://github.com/SatoshiAndKin/ypricemagic-server/issues/41)) ([92407d5](https://github.com/SatoshiAndKin/ypricemagic-server/commit/92407d58e5bb7f3cf6067b8ab7eb9d5cb4a6ad7c))
* separate dev and prod compose stacks to simplify local builds and rollout deploys ([#48](https://github.com/SatoshiAndKin/ypricemagic-server/issues/48)) ([da42445](https://github.com/SatoshiAndKin/ypricemagic-server/commit/da42445039e92d5afa954eaad6dd6db26babfffe))
* split into API backend + Svelte frontend + Traefik infrastructure ([#43](https://github.com/SatoshiAndKin/ypricemagic-server/issues/43)) ([029570e](https://github.com/SatoshiAndKin/ypricemagic-server/commit/029570e0510adb8fb69c23b9df75d870bc79dbfb))
* token autocomplete, tokenlist management, and zero-downtime deploy ([#35](https://github.com/SatoshiAndKin/ypricemagic-server/issues/35)) ([4f726fb](https://github.com/SatoshiAndKin/ypricemagic-server/commit/4f726fbcad0046ff9be4c131edb05c82a7a70549))
* update ypricemagic and expose trade path in API responses ([#38](https://github.com/SatoshiAndKin/ypricemagic-server/issues/38)) ([5377285](https://github.com/SatoshiAndKin/ypricemagic-server/commit/53772856edd1bb6c185a994c7b7fd76362d7d296))


### Bug Fixes

* add explicit proxy network so Traefik can reach all backends ([#47](https://github.com/SatoshiAndKin/ypricemagic-server/issues/47)) ([7bd39c0](https://github.com/SatoshiAndKin/ypricemagic-server/commit/7bd39c0213757513cfdb136e03996a4dd43c60d9))
* build+push frontend image and remove broken deploy job ([#56](https://github.com/SatoshiAndKin/ypricemagic-server/issues/56)) ([b6fbc73](https://github.com/SatoshiAndKin/ypricemagic-server/commit/b6fbc7319dbd4803d396abac37ec7ffb180ccdd4))
* bundle Uniswap default tokenlist instead of fetching at runtime ([#54](https://github.com/SatoshiAndKin/ypricemagic-server/issues/54)) ([27b3266](https://github.com/SatoshiAndKin/ypricemagic-server/commit/27b326604cb56d8cc539b373c252402be0757628))
* cap dank_mids EXTRA_QUEUED_CALLS on macOS to avoid SEM_VALUE_MAX crash ([#40](https://github.com/SatoshiAndKin/ypricemagic-server/issues/40)) ([4f032cc](https://github.com/SatoshiAndKin/ypricemagic-server/commit/4f032cc5b5958f62915bdf0173a9f877a20e9bea))
* default quote amount and pin Python 3.12 ([#51](https://github.com/SatoshiAndKin/ypricemagic-server/issues/51)) ([6c5afbf](https://github.com/SatoshiAndKin/ypricemagic-server/commit/6c5afbfc3151b021a3b0aec7d9d20ecf89aff9c1))
* move httpx to main dependencies so it is installed in production ([#46](https://github.com/SatoshiAndKin/ypricemagic-server/issues/46)) ([fa5bbfe](https://github.com/SatoshiAndKin/ypricemagic-server/commit/fa5bbfebc1469cfca8916b0441926586f05fcbcc))
* repair chain docs and simplify frontend ([#52](https://github.com/SatoshiAndKin/ypricemagic-server/issues/52)) ([bb1d0e8](https://github.com/SatoshiAndKin/ypricemagic-server/commit/bb1d0e8daf754d9c00e3291c25ece85d3ee6b309))
* upgrade vitest to ^4 to match @vitest/coverage-v8 peer dep ([#45](https://github.com/SatoshiAndKin/ypricemagic-server/issues/45)) ([4ac7239](https://github.com/SatoshiAndKin/ypricemagic-server/commit/4ac72396b378f4c73094e8ddb1eaef7db0fcc502))
* use env_file in docker-stack.yml for swarm compatibility ([#42](https://github.com/SatoshiAndKin/ypricemagic-server/issues/42)) ([f6430b6](https://github.com/SatoshiAndKin/ypricemagic-server/commit/f6430b627fa82d2137322e7fa6483623903e80ff))
* use ghcr frontend image in prod compose instead of local build ([#55](https://github.com/SatoshiAndKin/ypricemagic-server/issues/55)) ([aea2656](https://github.com/SatoshiAndKin/ypricemagic-server/commit/aea26564f5537096cfcf9d6a95cad3cc31c1b3df))

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
