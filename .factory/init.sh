#!/bin/bash
set -e

cd /Users/bryan/code/ypricemagic-server

# Install backend dependencies (idempotent)
uv sync --extra dev

# Install frontend dependencies (idempotent)
cd frontend && npm install
