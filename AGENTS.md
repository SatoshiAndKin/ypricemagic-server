# AGENTS.md — ypricemagic-server

Multi-chain ERC-20 token price API backed by [ypricemagic](https://github.com/BobTheBuidler/ypricemagic). One container per chain, routed through Traefik.

## Environment Setup

```bash
cp env.example .env
# Edit .env with your RPC URLs and ETHERSCAN_TOKEN
uv sync --extra dev
```

## Running

```bash
docker compose up --build
```

API available at `http://localhost:8000`. Interactive UI at `/`.

## Development Commands

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy src/

# Check unused dependencies
uv run deptry .

# Install pre-commit hooks
uv run pre-commit install
```

> **Note on pkg_resources**: The venv requires `setuptools<82` for brownie compatibility. The dev dependencies include this. If you see `ModuleNotFoundError: No module named 'pkg_resources'`, run `uv sync --extra dev`.

## Project Layout

```
src/
  server.py      # FastAPI app, lifespan, price/health/batch/bucket endpoints
  cache.py       # diskcache-backed price cache (keyed by token:block)
  params.py      # Input validation (token address, block number, timestamps)
  logger.py      # structlog configuration with secret redaction
  tests/         # pytest tests (test_server, test_params, test_cache, test_logger, test_static)
frontend/        # Svelte 5 + Vite browser UI (separate Docker image)
scripts/         # validate_prices.py, export_openapi.py, update_tokenlist.py, deploy.sh
traefik-proxy/   # Shared Traefik reverse proxy config
.github/
  workflows/     # CI (tests+lint), Docker publish, release-please, PR review
```

## API Endpoints

All endpoints are chain-scoped via path prefix (`/{chain}/...`), routed by Traefik.

- `GET /{chain}/price?token=<address>&block=<block>` — single token USD price (optional: `to`, `amount`, `timestamp`, `skip_cache`, `ignore_pools`)
- `GET /{chain}/prices?tokens=<addr1>,<addr2>&block=<block>` — batch USD pricing
- `GET /{chain}/check_bucket?token=<address>` — token pricing bucket classification
- `GET /health` — aggregate health (proxied to ethereum backend)
- `GET /{chain}/health` — per-chain health
- `GET /` — browser UI (served by frontend container)

## Supported Chains

`ethereum` (1), `arbitrum` (42161), `optimism` (10), `base` (8453)

## Architecture

```
client → traefik-proxy:8000 → frontend:8080
                             → ypm-ethereum:8001
                             → ypm-arbitrum:8001
                             → ypm-optimism:8001
                             → ypm-base:8001
```

Each chain container: brownie network connect → dank_mids patch → uvicorn FastAPI server.

## Git Workflow

- **Never commit directly to main.** Always create a feature branch, push it, and open a PR.
- Use the `/commit-push-pr` command to commit, push, and create PRs.
- Branch naming: `<type>/<short-description>` (e.g. `fix/release-please-config`, `feat/new-endpoint`, `chore/update-deps`).
- Use squash merges via `gh pr merge --squash`.

## Code Conventions

- Python 3.12, managed by [uv](https://github.com/astral-sh/uv)
- **Formatting**: `ruff format` (double quotes, 4-space indent, 100 char line length)
- **Linting**: `ruff check` with pyflakes, bugbear, pep8-naming, complexity ≤10
- **Types**: mypy strict — all public functions must have type annotations
- **Naming**: snake_case for functions/variables, PascalCase for classes (enforced by ruff N rules)
- **Tests**: pytest, files named `test_*.py`, classes `Test*`, functions `test_*`
- **Error handling**: never silently swallow exceptions that affect correctness; cache failures are non-fatal (log warning, continue)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RPC_URL_ETHEREUM` | yes | Ethereum RPC endpoint |
| `RPC_URL_ARBITRUM` | yes | Arbitrum RPC endpoint |
| `RPC_URL_OPTIMISM` | yes | Optimism RPC endpoint |
| `RPC_URL_BASE` | yes | Base RPC endpoint |
| `ETHERSCAN_TOKEN` | yes | Etherscan API key (used for all explorer APIs) |
| `PORT` | no | External port for Traefik proxy (default: 8000) |
| `CACHE_DIR` | no | Path for diskcache storage (default: /data/cache) |
| `CHAIN_NAME` | container | Set per-container by docker-compose |
| `CHAIN_ID` | container | Set per-container by docker-compose |
| `RPC_URL` | container | Set per-container from RPC_URL_<CHAIN> |

## Lessons Learned

- **Pre-release transitive build deps**: `prerelease = "allow"`, `UV_PRERELEASE=allow`, and `--prerelease=allow` do NOT propagate into PEP 517 build isolation environments. If a git/source dependency has pre-release transitive build deps (e.g., ypricemagic's build-system.requires pulls eth-brownie which needs cchecksum==0.3.7.dev0), you must use `build-constraint-dependencies` in `[tool.uv]` to pin them. `extra-build-dependencies` alone is NOT sufficient.
- **Git deps need git in Docker**: If any dependency uses a git source (e.g., `ypricemagic @ git+https://...`), the Dockerfile must install `git` via apt-get.
- **PyPI wheels vs git source builds**: PyPI packages install from pre-built wheels (no build env needed). Switching to a git source requires building from source, which triggers `build-system.requires` resolution -- a completely different code path that can surface new dependency issues.

## CI/CD

- **CI** (`ci.yml`): runs on all PRs — ruff lint, ruff format check, mypy, pytest with coverage
- **Docker publish** (`docker-publish.yml`): builds and pushes to ghcr.io on merge to main
- **Release** (`release.yml`): release-please automation creates versioned releases
- **PR review** (`pr-review.yml`): Trivy security scan + CodeQL analysis on every PR
