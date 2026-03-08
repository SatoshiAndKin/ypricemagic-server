---
name: infra-worker
description: Infrastructure worker for Traefik, docker-rollout, and deployment in ypricemagic-server
---

# Infrastructure Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for infrastructure features: Traefik configuration, docker-compose.yml rewrite, Dockerfile updates, deploy scripts, removing nginx/Swarm files, environment config.

## Key Technology Context

**Traefik v3** replaces nginx:
- Auto-discovers Docker containers via labels on the Docker socket
- Routing rules defined as container labels, not config files
- StripPrefix middleware for chain prefix removal
- `--providers.docker.exposedbydefault=false` requires opt-in via `traefik.enable=true`

**docker-rollout** requirements:
- No `container_name` on rollable services (prevents scaling)
- No `ports` mapping on rollable services (conflicts when scaling, Traefik handles external exposure)
- Docker healthchecks required (rollout waits for healthy before draining old)
- Container draining: healthcheck includes `test ! -f /tmp/drain`, pre-stop hook touches `/tmp/drain`
- `stop_grace_period` >= 30s for in-flight requests

## Work Procedure

### 1. Understand the Feature

Read the feature description, preconditions, expectedBehavior, verificationSteps, and fulfills. Read AGENTS.md for boundaries (port ranges, off-limits resources). Check `.factory/library/environment.md` and `.factory/library/architecture.md`.

### 2. Read Existing Infrastructure

- `docker-compose.yml` — current service definitions
- `docker-stack.yml` — Swarm config (to be removed)
- `nginx.conf` — current routing (to be replaced by Traefik labels)
- `Dockerfile` — backend build process
- `setup-networks.sh` — container entrypoint (must still work)
- `env.example` — environment variable documentation
- `scripts/` — existing scripts (strip_depends_on.py is Swarm-only, candidate for removal)
- `.factory/research/` — Traefik and docker-rollout research (if available)

### 3. Implement

**For Traefik docker-compose.yml:**
```yaml
# Key patterns:
services:
  traefik:
    image: traefik:v3.2
    container_name: traefik  # OK — traefik itself is never rolled out
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--ping=true"
      - "--api.dashboard=false"
    ports:
      - "${PORT:-8000}:80"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"

  ypm-ethereum:
    # NO container_name
    # NO ports
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ethereum.entrypoints=web"
      - "traefik.http.routers.ethereum.rule=PathPrefix(`/ethereum`)"
      - "traefik.http.routers.ethereum.middlewares=strip-ethereum"
      - "traefik.http.middlewares.strip-ethereum.stripprefix.prefixes=/ethereum"
      - "traefik.http.services.ethereum.loadbalancer.server.port=8001"
    healthcheck:
      test: ["CMD-SHELL", "test ! -f /tmp/drain && curl -sf http://localhost:8001/health"]
      interval: 10s
      timeout: 10s
      retries: 3
      start_period: 60s
    stop_grace_period: 30s

  frontend:
    # Serves built Svelte app via nginx
    # NO container_name (rollable)
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.entrypoints=web"
      - "traefik.http.routers.frontend.rule=PathPrefix(`/`)"
      - "traefik.http.routers.frontend.priority=1"  # lowest priority (chain routes take precedence)
      - "traefik.http.services.frontend.loadbalancer.server.port=8080"
```

**For chain routing:**
- Each chain gets a PathPrefix router + StripPrefix middleware
- Chain routers have higher priority than frontend catch-all (default priority by rule length handles this)
- The `/tokenlist/proxy` endpoint must be routable — it uses `/{chain}/tokenlist/proxy` since it goes through a chain backend

**For deploy script:**
```bash
#!/usr/bin/env bash
set -eux -o pipefail
docker compose pull
docker compose build
for svc in ypm-ethereum ypm-arbitrum ypm-optimism ypm-base frontend; do
  docker rollout "$svc"
done
```

### 4. Run Validators

```bash
docker compose config  # validates compose YAML
bash -n scripts/deploy.sh  # syntax check
uv run pytest -x -q  # existing tests still pass
grep -c container_name docker-compose.yml  # should be 1 (traefik only)
```

### 5. Manual Verification

- `docker compose config` — validates
- Review labels carefully: each chain has correct PathPrefix, StripPrefix, and port
- Verify no `container_name` on rollable services
- Verify no `ports` on backend/frontend services
- Verify healthchecks include drain check (`test ! -f /tmp/drain`)
- Verify `stop_grace_period` >= 30s on all chain services
- Verify `docker-stack.yml` and `nginx.conf` are deleted
- If Docker is available: `docker compose up -d` and test routing with curl

### 6. Commit

Commit all changes with a clear message.

## Example Handoff

```json
{
  "salientSummary": "Replaced nginx+Swarm with Traefik v3 docker-compose.yml. All 4 chain services have Traefik labels with PathPrefix routing and StripPrefix middleware. Frontend served at / with lowest priority. No container_name on rollable services. Drain-compatible healthchecks. Deleted docker-stack.yml, nginx.conf, strip_depends_on.py. Created scripts/deploy.sh with docker-rollout commands. docker compose config validates.",
  "whatWasImplemented": "New docker-compose.yml with Traefik v3 service (Docker provider, ping enabled, dashboard disabled), 4 chain backend services (ethereum, arbitrum, optimism, base) with Traefik labels, frontend service with catch-all route at priority 1. All rollable services: no container_name, no ports, healthcheck with drain support, stop_grace_period 30s. Deploy script loops through services with docker rollout. Removed nginx.conf, docker-stack.yml, scripts/strip_depends_on.py. Updated env.example.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "docker compose config", "exitCode": 0, "observation": "Valid compose file"},
      {"command": "bash -n scripts/deploy.sh", "exitCode": 0, "observation": "Syntax OK"},
      {"command": "grep container_name docker-compose.yml", "exitCode": 0, "observation": "Only traefik has container_name"},
      {"command": "uv run pytest -x -q", "exitCode": 0, "observation": "301 passed"}
    ],
    "interactiveChecks": [
      {"action": "Reviewed Traefik labels for all 4 chains", "observed": "Correct PathPrefix, StripPrefix, port 8001 for each"},
      {"action": "Verified no ports on backend/frontend services", "observed": "Only traefik exposes PORT:80"},
      {"action": "Verified docker-stack.yml and nginx.conf deleted", "observed": "Both files removed"}
    ]
  },
  "tests": {"added": []},
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Docker daemon is not available or OrbStack is not running
- Port conflicts that can't be resolved within mission boundaries
- Traefik label syntax is unclear for a specific routing pattern
- Docker build fails due to upstream dependency issues
- Need to modify backend Python code beyond what the feature describes
