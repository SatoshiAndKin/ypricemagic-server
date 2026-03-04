# ypricemagic-server

A multi-chain token price API backed by [ypricemagic](https://github.com/BobTheBuidler/ypricemagic). One container runs per chain; an nginx reverse proxy routes requests by chain-prefixed paths (`/<chain>/...`).

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

### `GET /{chain}/price`

Fetch the USD price for a single token on a specific chain.

| Parameter | In | Required | Description |
|-----------|----|----------|-------------|
| `chain` | path | yes | `ethereum`, `arbitrum`, `optimism`, or `base` |
| `token` | query | yes | ERC-20 token address (`0x...`) |
| `block` | query | no | Block number; mutually exclusive with `timestamp` |
| `timestamp` | query | no | Unix epoch or ISO-8601 timestamp; resolves to a block |
| `amount` | query | no | Human-readable token amount for amount-aware pricing |
| `skip_cache` | query | no | `true` to bypass disk cache |
| `ignore_pools` | query | no | Comma-separated pool addresses to exclude |
| `silent` | query | no | `true` to suppress verbose upstream logging |

**Response schema (`200`):**

```json
{
  "chain": "ethereum",
  "token": "0x...",
  "block": 21900000,
  "price": 1.0,
  "cached": false,
  "block_timestamp": 1740000000,
  "amount": 1000.0
}
```

`amount` is only present when provided in the request.

### `GET /{chain}/prices`

Batch USD pricing for multiple tokens.

| Parameter | In | Required | Description |
|-----------|----|----------|-------------|
| `chain` | path | yes | `ethereum`, `arbitrum`, `optimism`, or `base` |
| `tokens` | query | yes | Comma-separated ERC-20 token addresses |
| `block` | query | no | Block number; mutually exclusive with `timestamp` |
| `timestamp` | query | no | Unix epoch or ISO-8601 timestamp; resolves to a block |
| `amounts` | query | no | Comma-separated amounts aligned with `tokens` order |
| `skip_cache` | query | no | `true` to bypass disk cache |
| `silent` | query | no | `true` to suppress verbose upstream logging |

**Response schema (`200`):**

```json
[
  {
    "token": "0x...",
    "block": 21900000,
    "price": 1.0,
    "block_timestamp": 1740000000,
    "cached": false
  }
]
```

Tokens that fail pricing return `"price": null` while the endpoint still returns `200`.

### `GET /{chain}/quote`

From→to token quoting endpoint for swap-style quote flows.

| Parameter | In | Required | Description |
|-----------|----|----------|-------------|
| `chain` | path | yes | `ethereum`, `arbitrum`, `optimism`, or `base` |
| `from` | query | yes | Input token address |
| `to` | query | yes | Output token address |
| `amount` | query | yes | Input token amount |
| `block` | query | no | Historical block number |
| `timestamp` | query | no | Historical Unix epoch timestamp (resolved to block) |

**Response schema (`200`):**

```json
{
  "from": "0x...",
  "to": "0x...",
  "amount": 1000.0,
  "output_amount": 0.357,
  "block": 21900000,
  "chain": "ethereum",
  "block_timestamp": 1740000000,
  "route": "divide"
}
```

#### `curl` examples for `/quote`

**Basic quote:**

```bash
curl "http://localhost:8000/ethereum/quote?from=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48&to=0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2&amount=1000"
```

**Historical quote at a block:**

```bash
curl "http://localhost:8000/ethereum/quote?from=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48&to=0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2&amount=1000&block=18000000"
```

**Historical quote at a timestamp:**

```bash
curl "http://localhost:8000/ethereum/quote?from=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48&to=0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2&amount=1000&timestamp=1693526400"
```

### `GET /{chain}/check_bucket`

Returns the ypricemagic pricing bucket classification for a token (for example `"stable"`, `"curve lp"`, `"atoken"`).

| Parameter | In | Required | Description |
|-----------|----|----------|-------------|
| `chain` | path | yes | `ethereum`, `arbitrum`, `optimism`, or `base` |
| `token` | query | yes | ERC-20 token address |

**Response schema (`200`):**

```json
{
  "token": "0x...",
  "chain": "ethereum",
  "bucket": "stable"
}
```

### `GET /health`

Aggregate health check (proxied to ethereum backend).

| Parameter | In | Required | Description |
|-----------|----|----------|-------------|
| _none_ | — | — | No parameters |

**Response schema (`200`):**

```json
{
  "status": "ok",
  "chain": "ethereum",
  "block": 21900000,
  "synced": true
}
```

### `GET /health/<chain>`

Per-chain health check (externally reached as `GET /<chain>/health`, for example `/arbitrum/health`).

| Parameter | In | Required | Description |
|-----------|----|----------|-------------|
| `chain` | path | yes | `ethereum`, `arbitrum`, `optimism`, or `base` |

**Response schema (`200`):** same schema as `GET /health`.

### From→to quoting workflow

1. Resolve a target block (`latest`, explicit `block`, or block resolved from `timestamp`).
2. Attempt direct route/path pricing when available.
3. Fall back to divide strategy (`output_amount = amount × (price_from / price_to)`) when no direct route is available.
4. Return `route` to indicate strategy (`divide`) plus `block_timestamp` for price age displays.
5. When `amount` is set, quotes are more likely to be uncached and may take longer.

## Browser UI

The root path (`/`) serves an interactive browser UI for all API endpoints.

### Quote UI screenshot (latest block)

![Latest-block USDC→crvUSD quote result with price age in seconds](docs/readme-quote-latest-block.png)

### Theme toggle (light / dark / system)

The header includes a theme toggle with three modes: `system` (default), `light`, and `dark`. The selected mode is persisted in local storage. Quote/result sections, tokenlist modal, and related chart-friendly historical views are styled for both light and dark mode.

### Token autocomplete

All token address inputs support autocomplete. Type a symbol, name, or address to search across loaded tokenlists. Results are filtered by the currently selected chain. If you submit an address that isn't in any enabled tokenlist, a warning modal lets you proceed anyway or add the token to your local list.

Autocomplete works in the quote, batch, and bucket forms.

### Tokenlist management

Click the gear icon (⚙) in the header to open the tokenlist manager. From there you can:

- View loaded tokenlists and toggle them on/off
- Add a new tokenlist by URL (HTTPS only)
- Import a tokenlist from a JSON file
- Export the locally-saved tokenlist
- Delete custom tokenlists

All tokenlist state is stored in `localStorage`. The [Uniswap Default tokenlist](https://tokens.uniswap.org) is bundled at Docker build time and always available.

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
- **Docker** (`linux/amd64`) + Docker Compose + **Swarm** (zero-downtime deploy)
- **Uniswap tokenlist** — bundled token metadata for autocomplete

## Deployment

### Docker Compose (development)

```bash
docker compose up --build
```

### Docker Swarm (production)

The `docker-compose.yml` includes Swarm-compatible deploy configuration for zero-downtime deploys:

- **`update_config.order: start-first`** — new containers start before old ones stop (blue-green)
- **`rollback_config`** — automatic rollback on update failure
- **`stop_grace_period: 30s`** — allows in-flight requests to drain before shutdown
- **Health checks** gate traffic switching; nginx only routes to healthy backends

Brownie cache volumes (`brownie-<chain>`) persist across deploys so contract metadata doesn't need to be re-fetched.

To deploy manually:

```bash
docker swarm init  # one-time setup
docker compose config -o docker-stack.yml
python3 scripts/strip_depends_on.py docker-stack.yml  # strip extended depends_on for Swarm
docker stack deploy -c docker-stack.yml ypm --with-registry-auth
```

### CD pipeline

A GitHub Actions workflow (`.github/workflows/cd.yml`) runs on every push to `main`:

1. Builds and pushes the Docker image to `ghcr.io`
2. Copies the compose file to the server via SCP
3. Renders a Swarm-compatible compose file with `docker compose config`
4. Deploys via `docker stack deploy`
5. Polls `/health` to verify the deployment succeeded

Required GitHub Actions variables: `SSH_HOST`, `SSH_USER`, `SSH_KEY`.
