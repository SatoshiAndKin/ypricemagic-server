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

CATEGORY_MAP_ethereum="Ethereum"
CATEGORY_MAP_arbitrum="Arbitrum"
CATEGORY_MAP_optimism="Optimistic Ethereum"
CATEGORY_MAP_base="Base"
CATEGORY_MAP_polygon="Polygon"

CATEGORY_VAR="CATEGORY_MAP_${CHAIN_NAME}"
CATEGORY="${!CATEGORY_VAR:-}"

if [ -z "$CATEGORY" ]; then
  echo "ERROR: Unsupported CHAIN_NAME: ${CHAIN_NAME}"
  echo "Supported chains: ethereum, arbitrum, optimism, base, polygon"
  exit 1
fi

echo "Registering brownie network: id=${NETWORK_ID} host=${RPC_URL} chainid=${CHAIN_ID}"

ADD_ARGS="brownie networks add \"${CATEGORY}\" ${NETWORK_ID} host=${RPC_URL} chainid=${CHAIN_ID}"
if [ -n "$EXPLORER" ]; then
  ADD_ARGS="${ADD_ARGS} explorer=${EXPLORER}"
fi

OUTPUT=$(eval $ADD_ARGS 2>&1) || {
  if echo "$OUTPUT" | grep -qi "already exists"; then
    echo "Network ${NETWORK_ID} already exists, continuing..."
  else
    echo "ERROR: Failed to register brownie network ${NETWORK_ID}"
    echo "$OUTPUT"
    exit 1
  fi
}

if ! brownie networks list 2>/dev/null | grep -q "${NETWORK_ID}"; then
  echo "ERROR: Network ${NETWORK_ID} not found after registration"
  exit 1
fi

echo "Network ${NETWORK_ID} registered successfully"

export BROWNIE_NETWORK_ID="${NETWORK_ID}"

exec uvicorn src.server:app --host 0.0.0.0 --port 8001 --loop asyncio
