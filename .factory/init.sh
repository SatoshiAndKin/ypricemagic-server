#!/usr/bin/env bash
set -eux -o pipefail

cd /Users/bryan/code/ypricemagic-server

# Install Python dependencies
uv sync --extra dev

# Install frontend dependencies (if frontend/ exists)
if [ -d frontend ] && [ -f frontend/package.json ]; then
  cd frontend
  npm install
  cd ..
fi

# Download Uniswap tokenlist for local dev (gitignored, downloaded at build time in Docker)
if [ ! -f static/tokenlists/uniswap-default.json ]; then
  mkdir -p static/tokenlists
  curl -sf https://tokens.uniswap.org -o static/tokenlists/uniswap-default.json
  echo "Downloaded Uniswap tokenlist"
fi

# Also ensure frontend has the tokenlist
if [ -d frontend/public/tokenlists ] && [ ! -f frontend/public/tokenlists/uniswap-default.json ]; then
  cp static/tokenlists/uniswap-default.json frontend/public/tokenlists/uniswap-default.json
  echo "Copied Uniswap tokenlist to frontend"
fi
