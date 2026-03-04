# User Testing

## Testing Surface

- **URL**: http://localhost:8000 (docker compose dev, ETH only)
- **Tool**: agent-browser for visual verification, curl for API endpoints
- **Start**: `docker compose up -d --build` (builds locally, starts ETH chain + nginx)
- **Health check**: `curl -sf http://localhost:8000/ethereum/health`
- **Stop**: `docker compose down`

## Test Tokens (Ethereum mainnet, in Uniswap default tokenlist)

| Symbol | Address | Has Logo |
|--------|---------|----------|
| DAI | 0x6B175474E89094C44Da98b954EedeAC495271d0F | Yes |
| USDC | 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 | Yes |
| WETH | 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 | Yes |
| UNI | 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984 | Yes |

## Notes

- Dev compose is ETH only. /arbitrum/, /optimism/, /base/ routes return 502 JSON.
- First Docker build takes ~60s due to mypyc compilation of ypricemagic.
- Price lookups require a working RPC connection to the Ethereum node.
