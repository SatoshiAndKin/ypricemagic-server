# ypricemagic-server

A multi-chain token price API backed by [ypricemagic](https://github.com/BobTheBuidler/ypricemagic). One container runs per chain; an nginx reverse proxy routes requests by `?chain=` parameter.

## Architecture

```
client → nginx:8000 → ypm-ethereum:8001
                    → ypm-arbitrum:8001
                    → ypm-optimism:8001
                    → ypm-base:8001
```

Each chain container runs FastAPI + brownie + dank_mids + ypricemagic. Prices are cached to disk (diskcache) at `/data/cache`, keyed by `token:block`.

## Setup

Copy `env.example` to `.env` and fill in your RPC URLs and Etherscan API key:

```
RPC_URL_ETHEREUM=https://...
RPC_URL_ARBITRUM=https://...
RPC_URL_OPTIMISM=https://...
RPC_URL_BASE=https://...
ETHERSCAN_TOKEN=your_etherscan_api_key
PORT=8000
```

## Running

```bash
docker compose up --build
```

The API is available at `http://localhost:8000` (or `$PORT`). A browser UI is served at `/`.

## API

All requests go through nginx on port 8000. An interactive browser UI is served at `/`.

### `GET /price`

Fetch the USD price for a single token.

| Parameter      | Required | Description |
|----------------|----------|-------------|
| `chain`        | yes      | `ethereum`, `arbitrum`, `optimism`, or `base` |
| `token`        | yes      | ERC-20 token address (`0x...`) |
| `block`        | no       | Block number; defaults to latest. Mutually exclusive with `timestamp`. |
| `timestamp`    | no       | Unix epoch (e.g. `1700000000`) or ISO 8601 (e.g. `2023-11-14T22:13:20Z`). Resolves to a block via `get_block_at_timestamp`. Mutually exclusive with `block`. |
| `amount`       | no       | Human-readable token units for price-impact-aware pricing. |
| `skip_cache`   | no       | `true` to bypass the disk cache. |
| `ignore_pools` | no       | Comma-separated pool addresses to exclude from routing. |
| `silent`       | no       | `true` to suppress verbose upstream logging. |

**Example:**
```bash
curl "http://localhost:8000/price?chain=ethereum&token=<TOKEN_ADDR>"
```

**Response:**
```json
{
  "chain": "ethereum",
  "token": "<TOKEN_ADDR>",
  "block": 21900000,
  "price": 1.0,
  "cached": false,
  "block_timestamp": 1740000000
}
```

### `GET /prices`

Batch pricing — fetch USD prices for multiple tokens in one request.

| Parameter    | Required | Description |
|--------------|----------|-------------|
| `chain`      | yes      | Chain name |
| `tokens`     | yes      | Comma-separated ERC-20 token addresses |
| `block`      | no       | Block number; defaults to latest. Mutually exclusive with `timestamp`. |
| `timestamp`  | no       | Unix epoch or ISO 8601; resolves to a block. Mutually exclusive with `block`. |
| `amounts`    | no       | Comma-separated amounts (must match token order) |
| `skip_cache` | no       | `true` to bypass cache |
| `silent`     | no       | `true` to suppress verbose logging |

**Example:**
```bash
curl "http://localhost:8000/prices?chain=ethereum&tokens=<DAI_ADDR>,<USDC_ADDR>"
```

**Response:**
```json
[
  {
    "token": "<DAI_ADDR>",
    "block": 21900000,
    "price": 1.0,
    "block_timestamp": 1740000000,
    "cached": false
  },
  {
    "token": "<USDC_ADDR>",
    "block": 21900000,
    "price": 1.0,
    "block_timestamp": 1740000000,
    "cached": false
  }
]
```

Tokens that fail to price return `null` for `price` (HTTP 200 is still returned).

### `GET /check_bucket`

Returns the pricing bucket classification for a token (e.g. `"atoken"`, `"curve lp"`).

| Parameter | Required | Description |
|-----------|----------|-------------|
| `chain`   | yes      | Chain name |
| `token`   | yes      | ERC-20 token address |

**Example:**
```bash
curl "http://localhost:8000/check_bucket?chain=ethereum&token=<TOKEN_ADDR>"
```

**Response:**
```json
{
  "token": "<TOKEN_ADDR>",
  "chain": "ethereum",
  "bucket": "stable"
}
```

### `GET /health`

Returns health of the ethereum backend (representative aggregate check). Includes a `synced` field indicating node sync status (`true`, `false`, or `null` if unknown).

```json
{"status": "ok", "chain": "ethereum", "block": 21900000, "synced": true}
```

### `GET /health/{chain}`

Returns health of a specific chain backend (same response shape as `/health`).

## Supported Chains

| Chain     | Chain ID |
|-----------|----------|
| ethereum  | 1        |
| arbitrum  | 42161    |
| optimism  | 10       |
| base      | 8453     |

## Tech Stack

- **Python 3.12**, managed by [uv](https://github.com/astral-sh/uv)
- **ypricemagic** (latest master) — price resolution
- **brownie** — EVM network/web3 management
- **dank_mids** — batched async RPC calls
- **FastAPI** + **uvicorn** — HTTP server
- **diskcache** — persistent price cache
- **nginx** — reverse proxy / chain routing
- **Docker** (`linux/amd64`) + Docker Compose
