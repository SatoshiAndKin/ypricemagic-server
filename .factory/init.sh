#!/bin/bash
set -e

cd /Users/bryan/code/ypricemagic-server

# Install dependencies (idempotent)
uv sync
