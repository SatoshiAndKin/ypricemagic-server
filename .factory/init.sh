#!/usr/bin/env bash
set -eux -o pipefail

cd /Users/bryan/code/ypricemagic-server

# Install dependencies
uv sync --extra dev

# Ensure docker compose is running
if ! curl -sf http://localhost:8000/ethereum/health > /dev/null 2>&1; then
  echo "Docker compose not running or unhealthy. Starting..."
  docker compose up -d
  echo "Waiting for containers to be healthy (up to 90s)..."
  for i in $(seq 1 18); do
    if curl -sf http://localhost:8000/ethereum/health > /dev/null 2>&1; then
      echo "Containers healthy."
      break
    fi
    sleep 5
  done
fi
