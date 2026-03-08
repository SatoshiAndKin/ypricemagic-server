#!/usr/bin/env bash
set -eux -o pipefail

# Pull latest images and build
docker compose pull --ignore-pull-failures
docker compose build

# Rolling update each service
for service in ypm-ethereum ypm-arbitrum ypm-optimism ypm-base frontend; do
    docker rollout "$service"
done
