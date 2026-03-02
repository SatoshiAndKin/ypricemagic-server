# ypricemagic Unused Features Report

**Source**: `SatoshiAndKin/ypricemagic@master` (fork of `BobTheBuidler/ypricemagic`)
**Date**: 2026-03-02

## Fork-Specific Additions (2 commits ahead of upstream)

The SatoshiAndKin fork has **2 unique commits** not in upstream BobTheBuidler:

1. `587a434` — **feat: add `amount` parameter to `get_price`/`get_prices` for price impact** (Feb 26, 2026)
2. `298f604` — **docs: restore Examples docstrings removed in amount parameter commit** (Feb 26, 2026)

The `amount` parameter is **already used** by the server (`await get_price(token, block, amount=amount, sync=False)`).

---

## Complete `y` Module Public API (`__all__`)

### Currently USED by the server

| Export | Usage |
|--------|-------|
| `get_price` | `from y import get_price` — core pricing function |

### Currently NOT USED by the server

| Export | Type | Signature / Description |
|--------|------|------------------------|
| **`get_prices`** | function | `get_prices(token_addresses: Iterable[AnyAddressType], block: Block | None = None, *, fail_to_None: bool = False, skip_cache: bool = ENVS.SKIP_CACHE, silent: bool = False, amounts: Iterable[Decimal|int|float|None] | None = None) -> list[UsdPrice | None]` — Batch-price multiple tokens in parallel. Optimized for bulk queries. `amounts` param is fork-only (parallel to token_addresses for per-token price impact). |
| **`map_prices`** | function | `map_prices(token_addresses: Iterable[_TAddress], block: Block, *, fail_to_None: bool = False, skip_cache: bool = ENVS.SKIP_CACHE, silent: bool = False, amount: Decimal|int|float|None = None) -> a_sync.TaskMapping[_TAddress, UsdPrice | None]` — Returns an async TaskMapping of address→price. `amount` param is fork-only. |
| **`check_bucket`** | function | `check_bucket(token_address, sync=False) -> str` — Classifies a token into a pricing "bucket" (e.g. "atoken", "curve lp", "uni or uni-like lp", "chainlink feed", "stable usd", "stargate lp", etc.) |
| **`ERC20`** | class | `ERC20(address, asynchronous=True)` — ERC20 token wrapper with async `.symbol`, `.decimals`, `.name`, `.total_supply`, `.balance_of` etc. |
| **`LogFilter`** | class | Event log filter |
| **`Events`** | class | Decoded events filter |
| **`ProcessedEvents`** | class | Processed events filter |
| **`Contract`** | class | Brownie Contract wrapper/singleton |
| **`contract_creation_block`** | function | `contract_creation_block(address) -> int` — Find the block a contract was deployed |
| **`contract_creation_block_async`** | function | Async version of above |
| **`has_method`** | function | Check if a contract has a specific method |
| **`has_methods`** | function | Check if a contract has multiple methods |
| **`Network`** | enum | Network enum — `Network.Mainnet`, `Network.Optimism`, `Network.Arbitrum`, `Network.Base`, etc. |
| **`EEE_ADDRESS`** | constant | `0xEeee...eEEeE` — native ETH sentinel |
| **`WRAPPED_GAS_COIN`** | constant | WETH / wrapped native gas token address for current chain |
| **`weth`** | constant | WETH address |
| **`dai`** | constant | DAI address |
| **`usdc`** | constant | USDC address |
| **`wbtc`** | constant | WBTC address |
| **`magic`** | module | `y.prices.magic` module reference |
| **`raw_call`** | function | Low-level contract call helper |
| **`convert`** | module | Address conversion utilities (`convert.to_address_async`, etc.) |
| **`time`** | module | Block/timestamp utilities module |
| **`get_block_at_timestamp`** | function | `get_block_at_timestamp(timestamp: datetime.datetime) -> BlockNumber` — Find the block just before a timestamp |
| **`get_block_timestamp`** | function | `get_block_timestamp(height: int) -> int` — Get Unix timestamp of a block |
| **`get_block_timestamp_async`** | function | Async version of above |
| **`monkey_patches`** | module | Internal monkey patches module |

---

## `get_price` Full Signature (SatoshiAndKin fork)

```python
async def get_price(
    token_address: AnyAddressType,
    block: Block | None = None,
    *,
    fail_to_None: bool = False,        # NOT USED by server
    skip_cache: bool = ENVS.SKIP_CACHE, # NOT USED by server
    ignore_pools: tuple[Pool, ...] = (), # NOT USED by server
    silent: bool = False,               # NOT USED by server
    amount: Decimal | int | float | None = None,  # USED by server ✓
    sync: bool = True,                  # USED by server (sync=False) ✓
) -> UsdPrice | None
```

**Unused `get_price` parameters the server could leverage:**
- `fail_to_None=True` — return `None` instead of raising `yPriceMagicError` (server currently catches exceptions manually)
- `skip_cache=True` — bypass ypricemagic's internal disk cache
- `ignore_pools` — exclude specific DEX pools from pricing
- `silent=True` — suppress ypricemagic's internal error logging

## `get_prices` Full Signature (SatoshiAndKin fork)

```python
async def get_prices(
    token_addresses: Iterable[AnyAddressType],
    block: Block | None = None,
    *,
    fail_to_None: bool = False,
    skip_cache: bool = ENVS.SKIP_CACHE,
    silent: bool = False,
    amounts: Iterable[Decimal | int | float | None] | None = None,  # fork-only
    sync: bool = True,
) -> list[UsdPrice | None]
```

**Not used at all by the server.** Could enable a batch `/prices` endpoint.

## `map_prices` Full Signature (SatoshiAndKin fork)

```python
def map_prices(
    token_addresses: Iterable[_TAddress],
    block: Block,
    *,
    fail_to_None: bool = False,
    skip_cache: bool = ENVS.SKIP_CACHE,
    silent: bool = False,
    amount: Decimal | int | float | None = None,  # fork-only
) -> a_sync.TaskMapping[_TAddress, UsdPrice | None]
```

**Not used at all by the server.** Returns a streaming async TaskMapping.

---

## Time/Block Utilities (not used by server)

| Function | Signature | Use Case |
|----------|-----------|----------|
| `get_block_at_timestamp` | `(timestamp: datetime.datetime) -> BlockNumber` | Price-by-timestamp endpoint |
| `get_block_timestamp` | `(height: int) -> int` | Return block timestamps with prices |
| `get_block_timestamp_async` | `(height: int) -> int` | Async version |
| `closest_block_after_timestamp` | `(timestamp, wait_for_block_if_needed=False) -> BlockNumber` | Find block near a time |
| `last_block_on_date` | `(date: str | datetime.date) -> BlockNumber` | Historical date queries |
| `check_node` / `check_node_async` | `() -> None` | Health check (raises `NodeNotSynced`) |

---

## Recent Significant Upstream Commits (both repos)

| Date | PR/Commit | Description |
|------|-----------|-------------|
| Feb 17, 2026 | #1349 | **feat: add Stargate LP pricing via ratio** — new `stargate lp` bucket |
| Feb 22, 2026 | #1362 | **fix: surface actionable import-order error for dank_mids startup** — new `DankMidsImportOrderError` |
| Feb 26, 2026 | #1367 | **fix: support web3 v7 PoA middleware import path** |
| Feb 26, 2026 | #1355 | **chore: enable ez-a-sync mypy plugin** |
| Jan 29, 2026 | #1336 | **perf: rip out non-crucial high-memory startup caches** |
| Feb 6, 2026 | #1337 | **fix: trim uniswap v2 helper ignore_pools logging** |

---

## Environment Variables (ypricemagic-internal, not server env vars)

| Variable | Description |
|----------|-------------|
| `SKIP_CACHE` | Skip ypricemagic disk cache (default: False) |
| `CACHE_TTL` | RAM cache TTL for price lookups |
| `YPM_API_URL` | External ypriceapi URL (for federated pricing) |

---

## Summary: High-Value Unused Features for the Server

1. **`get_prices` / batch endpoint** — fetch prices for multiple tokens in one call, optimized for parallel execution
2. **`get_block_at_timestamp`** — enable a price-by-timestamp API (`/price?timestamp=...` instead of requiring block number)
3. **`fail_to_None` parameter** — simplify error handling in `_fetch_price` by using the library's own None-return mode
4. **`check_bucket`** — could expose token classification info in the API response
5. **`get_block_timestamp`** — return block timestamps alongside prices
6. **`ERC20` class** — could expose token metadata (symbol, decimals) in API responses
7. **`Network` enum** — could validate chain names against supported networks
8. **`check_node` / `check_node_async`** — could enhance health endpoint with node sync status
