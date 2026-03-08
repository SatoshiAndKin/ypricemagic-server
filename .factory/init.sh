#!/usr/bin/env bash
set -eu -o pipefail

cd /Users/bryan/code/ypricemagic-server

# Install Python dependencies
uv sync --extra dev

# Install frontend dependencies (if frontend/ exists)
if [ -d frontend ] && [ -f frontend/package.json ]; then
  (cd frontend && npm install)
fi

# Download Uniswap tokenlist for local dev
if [ ! -f static/tokenlists/uniswap-default.json ]; then
  mkdir -p static/tokenlists
  curl -sf https://tokens.uniswap.org -o static/tokenlists/uniswap-default.json || true
fi

# Copy tokenlist to frontend if needed
if [ -d frontend/public/tokenlists ] && [ -f static/tokenlists/uniswap-default.json ] && [ ! -f frontend/public/tokenlists/uniswap-default.json ]; then
  cp static/tokenlists/uniswap-default.json frontend/public/tokenlists/uniswap-default.json
fi
