#!/usr/bin/env bash
set -eux -o pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
export COMPOSE_FILE

# Pull prod images and rebuild the local frontend image
docker compose pull --ignore-pull-failures
docker compose build --pull always

# Rolling update each service
for service in ypm-ethereum ypm-arbitrum ypm-optimism ypm-base frontend; do
    docker rollout "$service"
done
