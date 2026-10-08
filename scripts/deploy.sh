#!/usr/bin/env bash
set -eux -o pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
export COMPOSE_FILE

# Pull prod images and rebuild the local frontend image
docker compose pull --ignore-pull-failures
docker compose build --pull always

# Roll out only the services enabled in this Compose configuration.
services=$(docker compose config --services)
while IFS= read -r service; do
    docker rollout "$service"
done <<< "$services"
