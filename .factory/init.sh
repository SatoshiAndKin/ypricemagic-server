#!/usr/bin/env bash
set -euo pipefail

cd /Users/bryan/code/ypricemagic-server

# Install dependencies (idempotent)
uv sync --extra dev
