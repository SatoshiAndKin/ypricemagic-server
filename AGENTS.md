# AGENTS.md — ypricemagic-server

Multi-chain ERC-20 token price API backed by [ypricemagic](https://github.com/BobTheBuidler/ypricemagic). One container per chain, routed through nginx.

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
  server.py      # FastAPI app, lifespan, price/health endpoints
  cache.py       # diskcache-backed price cache (keyed by token:block)
  params.py      # Input validation (token address, block number)
  tests/
    test_params.py  # Unit tests for params module
.github/
  workflows/     # CI (tests+lint), Docker publish, release-please, PR review
  ISSUE_TEMPLATE/
```

## API Endpoints

- `GET /price?chain=<chain>&token=<address>&block=<block>` — fetch token price
- `GET /health` — aggregate health (checks ethereum backend)
- `GET /health/<chain>` — per-chain health
- `GET /` — browser UI

## Supported Chains

`ethereum` (1), `arbitrum` (42161), `optimism` (10), `base` (8453), `polygon` (137)

## Architecture

```
client → nginx:8000 → ypm-ethereum:8001
                    → ypm-arbitrum:8001
                    → ypm-optimism:8001
                    → ypm-base:8001
                    → ypm-polygon:8001
```

Each chain container: brownie network connect → dank_mids patch → uvicorn FastAPI server.

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
| `RPC_URL_POLYGON` | yes | Polygon RPC endpoint |
| `ETHERSCAN_TOKEN` | yes | Etherscan API key (used for all explorer APIs) |
| `PORT` | no | External port for nginx (default: 8000) |
| `CACHE_DIR` | no | Path for diskcache storage (default: /data/cache) |
| `CHAIN_NAME` | container | Set per-container by docker-compose |
| `CHAIN_ID` | container | Set per-container by docker-compose |
| `RPC_URL` | container | Set per-container from RPC_URL_<CHAIN> |

## CI/CD

- **CI** (`ci.yml`): runs on all PRs — ruff lint, ruff format check, mypy, pytest with coverage
- **Docker publish** (`docker-publish.yml`): builds and pushes to ghcr.io on merge to main
- **Release** (`release.yml`): release-please automation creates versioned releases
- **PR review** (`pr-review.yml`): Trivy security scan + CodeQL analysis on every PR
