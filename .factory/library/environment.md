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
