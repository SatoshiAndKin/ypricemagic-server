# Environment

Environment variables, external dependencies, and setup notes.

**What belongs here:** Required env vars, external API keys/services, dependency quirks, platform-specific notes.
**What does NOT belong here:** Service ports/commands (use `.factory/services.yaml`).

---

## Python Environment

- Python 3.12, managed by uv
- Virtual env created by `uv sync --extra dev`
- setuptools<82 required for brownie compatibility

## ypricemagic Dependency

- Source: `git+https://github.com/SatoshiAndKin/ypricemagic.git@master`
- Fork of BobTheBuidler/ypricemagic with `amount` parameter support
- Build requires `cchecksum==0.3.7.dev0` (pre-release, specified in build-constraint-dependencies)
- Docker build requires `git` installed for cloning

## Docker

- OrbStack running on macOS
- .env file at repo root with RPC_URL_ETHEREUM, RPC_URL_ARBITRUM, RPC_URL_OPTIMISM, RPC_URL_BASE, ETHERSCAN_TOKEN
- Build is sensitive to dependency resolution — check [tool.uv] constraints if build fails
- **nginx restart after container recreation**: When chain containers are recreated (e.g., after `docker compose build`), nginx may cache stale DNS entries for the container hostnames. Run `docker compose restart nginx` after recreating containers to ensure proper routing.
