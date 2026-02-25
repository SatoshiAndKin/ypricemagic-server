# ypricemagic-server

A multi-chain token price API backed by [ypricemagic](https://github.com/BobTheBuidler/ypricemagic). One container runs per chain; an nginx reverse proxy routes requests by `?chain=` parameter.

## Architecture

```
client → nginx:8000 → ypm-ethereum:8001
                    → ypm-arbitrum:8001
                    → ypm-optimism:8001
                    → ypm-base:8001
                    → ypm-polygon:8001
```

Each chain container runs FastAPI + brownie + dank_mids + ypricemagic. Prices are cached to disk (diskcache) at `/data/cache`, keyed by `token:block`.

## Setup

Copy `env.example` to `.env` and fill in your RPC URLs and Etherscan API key:

```
RPC_URL_ETHEREUM=https://...
RPC_URL_ARBITRUM=https://...
RPC_URL_OPTIMISM=https://...
RPC_URL_BASE=https://...
RPC_URL_POLYGON=https://...
ETHERSCAN_TOKEN=your_etherscan_api_key
PORT=8000
```

## Running

```bash
docker compose up --build
```

The API is available at `http://localhost:8000` (or `$PORT`). A browser UI is served at `/`.

## API

All requests go through nginx on port 8000.

### `GET /price`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `chain`   | yes      | `ethereum`, `arbitrum`, `optimism`, `base`, or `polygon` |
| `token`   | yes      | ERC-20 token address (`0x...`) |
| `block`   | no       | Block number; defaults to latest |

**Example:**
```bash
curl "http://localhost:8000/price?chain=ethereum&token=0x6B175474E89094C44Da98b954EedeAC495271d0F"
```

**Response:**
```json
{
  "chain": "ethereum",
  "token": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
  "block": 21900000,
  "price": 1.0,
  "cached": false
}
```

### `GET /health`

Returns health of the ethereum backend (representative aggregate check).

### `GET /health/{chain}`

Returns health of a specific chain backend.

```bash
curl "http://localhost:8000/health/arbitrum"
```

```json
{"status": "ok", "chain": "arbitrum", "block": 123456789}
```

## Supported Chains

| Chain     | Chain ID |
|-----------|----------|
| ethereum  | 1        |
| arbitrum  | 42161    |
| optimism  | 10       |
| base      | 8453     |
| polygon   | 137      |

## Tech Stack

- **Python 3.12**, managed by [uv](https://github.com/astral-sh/uv)
- **ypricemagic 5.2.5** — price resolution
- **brownie** — EVM network/web3 management
- **dank_mids** — batched async RPC calls
- **FastAPI** + **uvicorn** — HTTP server
- **diskcache** — persistent price cache
- **nginx** — reverse proxy / chain routing
- **Docker** (`linux/amd64`) + Docker Compose
