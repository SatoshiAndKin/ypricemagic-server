---
name: infra-worker
description: Infrastructure worker for Docker, deploy scripts, and CI/CD in ypricemagic-server
---

# Infrastructure Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for features involving Docker configuration, docker-compose.yml, Dockerfile, Docker Swarm deploy config, GitHub Actions workflows, nginx configuration, volume management, health checks.

## Work Procedure

1. **Read the feature description** carefully. Understand what assertions this feature fulfills.

2. **Read existing infrastructure**:
   - `docker-compose.yml` — current service definitions, volumes, health checks
   - `Dockerfile` — build process, layers, entrypoint
   - `nginx.conf` — routing, proxy settings, timeouts
   - `setup-networks.sh` — container entrypoint
   - `.github/workflows/` — existing CI workflows
   - `.factory/library/environment.md` — env vars, platform notes

3. **Write tests first** (where applicable):
   - For deploy scripts: write the script with `set -eux -o pipefail` and test syntax with `bash -n`
   - For Docker changes: verify `docker compose config` validates after changes
   - For GitHub Actions: validate YAML syntax

4. **Implement the feature**:
   - Docker health checks must have reasonable timeouts and start_period
   - For Swarm deploy config: use `update_config.order: start-first` for blue-green, `stop_grace_period` for connection draining
   - Compose file MUST remain compatible with `docker compose up -d` for local dev (Compose ignores `deploy:` sections)
   - All scripts must be idempotent where possible
   - Any bash scripts MUST use `#!/usr/bin/env bash` and `set -eux -o pipefail`

5. **Run validators**:
   - `uv run pytest` — existing tests must pass
   - `docker compose config` — validates compose file
   - `bash -n scripts/deploy.sh` — syntax check for bash scripts
   - `uv run ruff check .` and `uv run mypy src/` for any Python changes

6. **Manual verification**:
   - For Docker volume changes: rebuild, verify volume mounts with `docker inspect`
   - For health check changes: `docker compose up -d`, watch logs, verify health status
   - For deploy script: review logic step-by-step (we don't run actual deploys in dev)
   - For CD workflow: validate YAML, check trigger conditions, review step logic

## Example Handoff

```json
{
  "salientSummary": "Added brownie cache volumes for all 4 chains, changed depends_on to service_healthy, created scripts/deploy.sh with rolling zero-downtime deploy logic, and added .github/workflows/cd.yml for automated deployment on push to main.",
  "whatWasImplemented": "docker-compose.yml: added brownie-<chain> named volumes mounted at /root/.brownie for all 4 chain services. Changed nginx depends_on from service_started to service_healthy. Created scripts/deploy.sh: loops through chains sequentially, pulls new image, starts new container with unique name, polls /health until 200, reloads nginx, sleeps 5s grace period, stops old container. Created .github/workflows/cd.yml: triggers on push to main, builds multi-platform image, pushes to ghcr.io, SSHes to server and runs deploy.sh.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      { "command": "docker compose config", "exitCode": 0, "observation": "valid compose file with brownie volumes" },
      { "command": "bash -n scripts/deploy.sh", "exitCode": 0, "observation": "syntax OK" },
      { "command": "grep service_healthy docker-compose.yml | wc -l", "exitCode": 0, "observation": "4 occurrences (one per chain)" },
      { "command": "uv run pytest", "exitCode": 0, "observation": "234 passed" }
    ],
    "interactiveChecks": [
      { "action": "docker compose up -d && docker inspect ypricemagic-server-ypm-ethereum-1 | grep brownie", "observed": "Volume mount visible at /root/.brownie" }
    ]
  },
  "tests": { "added": [] },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Need SSH credentials or server access details for CD workflow
- Docker build fails due to dependency issues
- Health check configuration conflicts with existing setup
- Deploy strategy needs architectural changes beyond what's described
