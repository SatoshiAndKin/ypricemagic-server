#!/bin/bash
set -e

if [ -z "$CHAIN_NAME" ] || [ -z "$RPC_URL" ] || [ -z "$CHAIN_ID" ]; then
  echo "ERROR: CHAIN_NAME, RPC_URL, and CHAIN_ID must be set"
  exit 1
fi

NETWORK_ID="${CHAIN_NAME}-custom"

EXPLORER_MAP_ethereum="https://api.etherscan.io/api"
EXPLORER_MAP_arbitrum="https://api.arbiscan.io/api"
EXPLORER_MAP_optimism="https://api-optimistic.etherscan.io/api"
EXPLORER_MAP_base="https://api.basescan.org/api"
EXPLORER_MAP_polygon="https://api.polygonscan.com/api"

EXPLORER_VAR="EXPLORER_MAP_${CHAIN_NAME}"
EXPLORER="${!EXPLORER_VAR:-}"

echo "Registering brownie network: id=${NETWORK_ID} host=${RPC_URL} chainid=${CHAIN_ID}"

CATEGORY_MAP_ethereum="Ethereum"
CATEGORY_MAP_arbitrum="Arbitrum"
CATEGORY_MAP_optimism="Optimistic Ethereum"
CATEGORY_MAP_base="Base"
CATEGORY_MAP_polygon="Polygon"

CATEGORY_VAR="CATEGORY_MAP_${CHAIN_NAME}"
CATEGORY="${!CATEGORY_VAR:-Ethereum}"

ADD_ARGS="brownie networks add ${CATEGORY} ${NETWORK_ID} host=${RPC_URL} chainid=${CHAIN_ID}"
if [ -n "$EXPLORER" ]; then
  ADD_ARGS="${ADD_ARGS} explorer=${EXPLORER}"
fi

eval $ADD_ARGS 2>/dev/null || echo "Network ${NETWORK_ID} may already exist, continuing..."

export BROWNIE_NETWORK_ID="${NETWORK_ID}"

exec uvicorn src.server:app --host 0.0.0.0 --port 8001
