# MCP server setup

ypricemagic exposes an OpenAPI spec on each chain endpoint. You can use [awslabs/openapi-mcp-server](https://github.com/awslabs/mcp/tree/main/src/openapi-mcp-server) to turn those specs into MCP tools that AI agents can call directly.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (provides `uvx`)

## Supported chains

| Chain    | Base URL                                    | OpenAPI spec                                            |
|----------|---------------------------------------------|---------------------------------------------------------|
| Ethereum | `https://ypricemagic.stytt.com/ethereum`    | `https://ypricemagic.stytt.com/ethereum/openapi.json`   |
| Arbitrum | `https://ypricemagic.stytt.com/arbitrum`    | `https://ypricemagic.stytt.com/arbitrum/openapi.json`   |
| Optimism | `https://ypricemagic.stytt.com/optimism`    | `https://ypricemagic.stytt.com/optimism/openapi.json`   |
| Base     | `https://ypricemagic.stytt.com/base`        | `https://ypricemagic.stytt.com/base/openapi.json`       |

## Configuration

Each chain needs its own MCP server entry because `awslabs.openapi-mcp-server` takes a single spec per instance. Add the following to your MCP config file:

- **Factory (Droid):** `~/.factory/mcp.json`
- **Claude Code:** `~/.claude/mcp.json`
- **Cursor:** `.cursor/mcp.json`
- **VS Code:** `.vscode/mcp.json`

```json
{
  "mcpServers": {
    "ypricemagic-ethereum": {
      "command": "uvx",
      "args": ["awslabs.openapi-mcp-server@latest"],
      "env": {
        "API_NAME": "ypricemagic-ethereum",
        "API_BASE_URL": "https://ypricemagic.stytt.com/ethereum",
        "API_SPEC_URL": "https://ypricemagic.stytt.com/ethereum/openapi.json",
        "LOG_LEVEL": "ERROR",
        "ENABLE_PROMETHEUS": "false",
        "ENABLE_OPERATION_PROMPTS": "true"
      }
    },
    "ypricemagic-arbitrum": {
      "command": "uvx",
      "args": ["awslabs.openapi-mcp-server@latest"],
      "env": {
        "API_NAME": "ypricemagic-arbitrum",
        "API_BASE_URL": "https://ypricemagic.stytt.com/arbitrum",
        "API_SPEC_URL": "https://ypricemagic.stytt.com/arbitrum/openapi.json",
        "LOG_LEVEL": "ERROR",
        "ENABLE_PROMETHEUS": "false",
        "ENABLE_OPERATION_PROMPTS": "true"
      }
    },
    "ypricemagic-optimism": {
      "command": "uvx",
      "args": ["awslabs.openapi-mcp-server@latest"],
      "env": {
        "API_NAME": "ypricemagic-optimism",
        "API_BASE_URL": "https://ypricemagic.stytt.com/optimism",
        "API_SPEC_URL": "https://ypricemagic.stytt.com/optimism/openapi.json",
        "LOG_LEVEL": "ERROR",
        "ENABLE_PROMETHEUS": "false",
        "ENABLE_OPERATION_PROMPTS": "true"
      }
    },
    "ypricemagic-base": {
      "command": "uvx",
      "args": ["awslabs.openapi-mcp-server@latest"],
      "env": {
        "API_NAME": "ypricemagic-base",
        "API_BASE_URL": "https://ypricemagic.stytt.com/base",
        "API_SPEC_URL": "https://ypricemagic.stytt.com/base/openapi.json",
        "LOG_LEVEL": "ERROR",
        "ENABLE_PROMETHEUS": "false",
        "ENABLE_OPERATION_PROMPTS": "true"
      }
    }
  }
}
```

If you only care about one chain, include just that entry.

## Adding a single chain quickly (Factory)

```bash
droid mcp add ypricemagic-ethereum \
  --command uvx \
  --args 'awslabs.openapi-mcp-server@latest' \
  --env API_NAME=ypricemagic-ethereum \
  --env API_BASE_URL=https://ypricemagic.stytt.com/ethereum \
  --env API_SPEC_URL=https://ypricemagic.stytt.com/ethereum/openapi.json \
  --env LOG_LEVEL=ERROR \
  --env ENABLE_PROMETHEUS=false \
  --env ENABLE_OPERATION_PROMPTS=true
```

Replace `ethereum` with the chain you want.

## What you get

The MCP server reads the OpenAPI spec and creates tools for each endpoint:

- **health** -- check API and RPC node status
- **price** -- get USD price (or token-to-token quote) for a single token at a block or timestamp
- **prices** -- batch-price up to 100 tokens in one call
- **check_bucket** -- classify a token into its pricing bucket (e.g. "atoken", "curve lp")

No auth is required. All endpoints are public.

## Troubleshooting

**"uvx: command not found"** -- install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**Server starts but no tools appear** -- check that the spec URL is reachable: `curl -s https://ypricemagic.stytt.com/ethereum/openapi.json | head -c 200`

**Timeout errors** -- price lookups can take up to 30 seconds for cold tokens. This is normal.
