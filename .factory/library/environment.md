# Environment

Environment variables, external dependencies, and setup notes.

**What belongs here:** Required env vars, external API keys/services, dependency quirks, platform-specific notes.
**What does NOT belong here:** Service ports/commands (use `.factory/services.yaml`).

---

## Required Environment Variables

See env.example. Key vars: RPC_URL_ETHEREUM, RPC_URL_ARBITRUM, RPC_URL_OPTIMISM, RPC_URL_BASE, ETHERSCAN_TOKEN.

## Platform Note

Docker images are built for linux/amd64. On Apple Silicon (arm64), they run under QEMU emulation which adds overhead. This is expected.

## Brownie Cache

Brownie stores contract ABIs and compilation artifacts at `/root/.brownie/` inside containers. This directory MUST be a persistent volume to avoid re-fetching ABIs on every deploy (Etherscan rate limit: 3 req/sec).

## Docker Swarm Deploy Gotchas

- `docker stack deploy` ignores Compose `build:` entries and requires an `image:` value for each deployed service.
- `docker stack deploy` does not automatically load `.env` files like `docker compose` does. Export variables first (for example `set -a && source .env && set +a`) or deploy a pre-rendered config.

## CD Workflow Notes

- The CD workflow (`.github/workflows/cd.yml`) sources `.env` on the server before `docker stack deploy` using `set -a && source .env && set +a`.
- `cancel-in-progress: false` prevents interrupting in-flight deploys.
- Post-deploy health verification polls `/health` endpoint with 30 retries at 10s intervals.
