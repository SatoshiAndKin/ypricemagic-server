#!/usr/bin/env bash
set -eux -o pipefail

cd /Users/bryan/code/ypricemagic-server

# Install dependencies
uv sync --extra dev

# Download Uniswap tokenlist for local dev (gitignored, downloaded at build time in Docker)
if [ ! -f static/tokenlists/uniswap-default.json ]; then
  mkdir -p static/tokenlists
  curl -sf https://tokens.uniswap.org -o static/tokenlists/uniswap-default.json
  echo "Downloaded Uniswap tokenlist"
fi

# Build and start docker compose (dev, ETH only)
if ! curl -sf http://localhost:8000/ethereum/health > /dev/null 2>&1; then
  echo "Docker compose not running or unhealthy. Building and starting..."
  docker compose up -d --build
  echo "Waiting for containers to be healthy (up to 120s)..."
  for i in $(seq 1 24); do
    if curl -sf http://localhost:8000/ethereum/health > /dev/null 2>&1; then
      echo "Containers healthy."
      break
    fi
    sleep 5
  done
fi
