# Tokenlist Format Reference

Standard Uniswap tokenlist format (https://github.com/Uniswap/token-lists).

---

## Top-Level Schema

```json
{
  "name": "Uniswap Labs Default",
  "version": { "major": 18, "minor": 6, "patch": 0 },
  "timestamp": "2026-02-24T17:16:49.996Z",
  "tokens": [...],
  "keywords": ["uniswap", "default"],
  "tags": {},
  "logoURI": "..."
}
```

## Token Entry

```json
{
  "chainId": 1,
  "address": "0x1111...1302",
  "name": "1inch",
  "symbol": "1INCH",
  "decimals": 18,
  "logoURI": "https://assets.coingecko.com/coins/images/13469/thumb/1inch-token.png",
  "extensions": {
    "bridgeInfo": {
      "10": { "tokenAddress": "0x<bridge-address>" }
    }
  }
}
```

Required fields: chainId, address, name, symbol, decimals. Optional: logoURI, tags, extensions.

## Chain ID Mapping (supported chains)

| Chain | chainId | Tokens in Uniswap list |
|-------|---------|----------------------|
| Ethereum | 1 | 357 |
| Optimism | 10 | 63 |
| Arbitrum | 42161 | 186 |
| Base | 8453 | 87 |

## Key Notes

- Unique key: (chainId, address) pair
- Addresses are EIP-55 checksummed but should be matched case-insensitively
- logoURI can be HTTPS or IPFS URI
- The `bridgeInfo` extension maps cross-chain equivalents
- Max 10,000 tokens per list
