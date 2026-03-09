#!/usr/bin/env bash
set -eu -o pipefail

cd /Users/bryan/code/ypricemagic-server

# Install Python dependencies
uv sync --extra dev

# Install frontend dependencies (if frontend/ exists)
if [ -d frontend ] && [ -f frontend/package.json ]; then
  (cd frontend && npm install)
fi
