# ypricemagic DEX Routing Analysis

## TL;DR

**ypricemagic DOES support multi-hop routing**, but with important caveats:
- **Uniswap V2**: Supports multi-hop via `get_path_to_stables()` which recursively builds swap paths through intermediate tokens. Also has a "deepest pool" fallback that prices the paired token recursively.
- **Uniswap V3**: Hardcodes exactly two path patterns: direct `TOKEN→USDC` and two-hop `TOKEN→WETH→USDC`. No recursive/dynamic multi-hop.
- **Neither V2 nor V3 tries arbitrary intermediary tokens** like USDT, WBTC, DAI as routing hops (except V2's recursive fallback, which is indirect).

The limitation for tokens like MIC is: if there's no liquid pool pairing MIC with a stablecoin OR with a token that itself has a known price, the price resolution fails. The system doesn't enumerate potential routing paths through USDT, WBTC, etc.

---

## Step-by-Step Price Resolution Flow

### 1. Entry Point: `y/prices/magic.py::_get_price()`

```
_get_price(token, block)
  → _get_price_from_api()       # try external API first
  → _exit_early_for_known_tokens()  # check "buckets" (atoken, curve LP, yearn, etc.)
  → _get_price_from_dexes()     # DEX price resolution (the focus of this analysis)
```

### 2. DEX Price Resolution: `_get_price_from_dexes()`

**File**: `y/prices/magic.py`

This function tries DEXes in order of liquidity depth:
1. **`uniswap_multiplexer`** (always first) — aggregates V1, all V2 forks, V3, V3 forks
2. **`curve`** (if available)
3. **`balancer_multiplexer`** (fallback if the above return nothing)

Each DEX reports its liquidity depth for the token. The function tries them from deepest to shallowest.

### 3. UniswapMultiplexer: `y/prices/dex/uniswap/uniswap.py`

The multiplexer aggregates all Uniswap-like routers:
- UniswapV1 (mainnet only)
- All V2 forks (uniswap v2, sushiswap, quickswap, etc.)
- UniswapV3 + V3 forks (velodrome slipstream, aerodrome, etc.)

It sorts them by liquidity depth and tries each one. The actual price logic lives in the individual router classes.

---

## Uniswap V2 Price Resolution (UniswapRouterV2.get_price)

**File**: `y/prices/dex/uniswap/v2.py`, method `UniswapRouterV2.get_price()`

This is the most complex and important code path. Here's the logic:

### Step A: Direct Stablecoin Check
```python
if token_in in STABLECOINS:
    return 1
```

### Step B: WETH → Stablecoin Direct Path
```python
if token_in in [weth.address, WRAPPED_GAS_COIN] and token_out in STABLECOINS:
    path = [token_in, token_out]
```

### Step C: Try `get_path_to_stables()` — **THIS IS THE MULTI-HOP LOGIC**
```python
if str(token_out) in STABLECOINS:
    path = await self.get_path_to_stables(token_in, block, ...)
```

**`get_path_to_stables()` is recursive and builds multi-hop paths:**
1. Find the "deepest pool" for the token (the pool with most liquidity of this token)
2. If the deepest pool IS a stablecoin pool → path = `[token, stablecoin]` (1-hop)
3. If the deepest pool is NOT a stablecoin pool → recursively call `get_path_to_stables(paired_token)` and prepend the current token
4. This recurse up to 10 times (`_loop_count > 10` guard)

**Example**: If MIC's deepest pool is MIC/USDT, and USDT is a stablecoin, path = `[MIC, USDT]`.
If MIC's deepest pool is MIC/WETH, and WETH's deepest stable pool is WETH/USDC, path = `[MIC, WETH, USDC]`.

**Critical insight**: `get_path_to_stables()` follows the **deepest pool chain** — it doesn't explore all possible intermediaries. It only follows the single deepest pool at each hop.

### Step D: "Deepest Pool" Fallback — **INDIRECT MULTI-HOP VIA RECURSIVE PRICING**
```python
if path is None and (deepest_pool := await self.deepest_pool(token_in, block, ...)):
    paired_with = await deepest_pool.get_token_out(token_in)
    path = [token_in, paired_with]
    quote = await self.get_quote(amount_in, path, block=block)
    # ... then recursively get price of paired_with:
    paired_with_price = await magic.get_price(paired_with, block, fail_to_None=True, ...)
    return amount_out * paired_with_price
```

This is the **key fallback**: if no path to stablecoins is found, it:
1. Finds the deepest pool for the token (any pool, not just stablecoin pairs)
2. Gets a quote: TOKEN → paired_token (single hop on-chain)
3. **Recursively calls `magic.get_price()` on the paired token** to get its USD price
4. Multiplies: `amount_out_of_paired_token × price_of_paired_token`

This means: **TOKEN → USDT works even if USDT isn't in `STABLECOINS`**, because it would get the quote for TOKEN→USDT, then recursively price USDT (which is $1).

### Step E: "Smol Brain" Fallback
```python
path = self._smol_brain_path_selector(token_in, token_out, paired_against)
```

Hardcoded fallback paths:
- `[token_in, WRAPPED_GAS_COIN, token_out]` — routes through WETH
- Special cases for BSC (WBNB, CAKE)
- Special paths from `SPECIAL_PATHS` config

### How V2 Gets the On-Chain Quote
```python
self.get_amounts_out = Call(self.address, "getAmountsOut(uint,address[])(uint[])").coroutine
```

This calls the Uniswap V2 Router's `getAmountsOut()` which **natively supports multi-hop paths**. So `[MIC, WETH, USDC]` would execute as a multi-hop quote through the router contract.

---

## Uniswap V3 Price Resolution (UniswapV3.get_price)

**File**: `y/prices/dex/uniswap/v3.py`, method `UniswapV3.get_price()`

### Hardcoded Path Patterns Only

```python
paths: list[Path] = [(token, fee, usdc.address) for fee in self.fee_tiers]
if token != weth:
    paths += [
        (token, fee, weth.address, self.fee_tiers[0], usdc.address)
        for fee in self.fee_tiers
    ]
```

**V3 only tries TWO patterns:**
1. **Direct**: `TOKEN →(fee)→ USDC` (for each fee tier: 100, 500, 3000, 10000)
2. **Two-hop via WETH**: `TOKEN →(fee)→ WETH →(3000)→ USDC` (for each fee tier)

**No other intermediaries are tried.** No USDT, no WBTC, no DAI.

### V3 Quoter Usage
Uses `quoteExactInput` with packed encoded paths:
```python
amount = await quoter.quoteExactInput.coroutine(
    _encode_path(path), amount_in, block_identifier=block
)
```

The V3 quoter natively supports multi-hop — the encoded path can contain multiple hops. But the code only ever passes 1-hop or 2-hop paths.

### V3 Returns the Best Price
```python
return UsdPrice(max(outputs) / _amount)
```

It takes the maximum output across all path variants.

---

## Token Pairing Logic Summary

### What token pairs are checked?

| Router | Pairing Strategy |
|--------|-----------------|
| V2 `get_path_to_stables()` | Follows the single deepest pool chain recursively until hitting a stablecoin |
| V2 "deepest pool" fallback | Any pool with the token; recursively prices the other token |
| V2 "smol brain" | `[TOKEN, WETH, USDC]` hardcoded |
| V3 | `[TOKEN, USDC]` and `[TOKEN, WETH, USDC]` only |
| Special paths | Hardcoded per-token paths in `v2_forks.py::SPECIAL_PATHS` |

### Base Tokens / Routing Tokens

**There is no explicit "base token" or "routing token" list.** The routing is implicit:
- **STABLECOINS** dict (`y/constants.py`): USDC, USDT, DAI, TUSD, SUSD etc. — used to detect when a swap path has reached USD
- **WRAPPED_GAS_COIN**: WETH/WBNB/WFTM etc. — used as the default intermediary in V2's `_smol_brain_path_selector` and V3's two-hop path
- **`weth`**: Used as explicit intermediary in V3 paths
- **`usdc`**: The target stablecoin for V3 price quotes
- **SPECIAL_PATHS**: Hardcoded multi-hop paths for specific tokens on sushiswap mainnet (e.g., `TOKEN → SUSHI → WETH → USDC`)

---

## Where the Limitation Exists

### The MIC Problem

For a token like MIC where:
- MIC/USDC pool has no/bad liquidity
- MIC/USDT pool exists with good liquidity
- MIC/WETH pool might not exist

**V2 would actually work** if:
- MIC/USDT is the deepest pool → `deepest_pool` fallback would get quote for MIC→USDT, then price USDT as $1. ✅
- OR: `get_path_to_stables()` finds the deepest pool is MIC/USDT and since USDT IS in STABLECOINS on mainnet, path = `[MIC, USDT]` ✅

**V3 would NOT work** because it only tries:
- `MIC→USDC` (no liquidity) ❌
- `MIC→WETH→USDC` (no MIC/WETH pool on V3) ❌
- **Never tries `MIC→USDT→USDC`** ❌

**Key files where the V3 limitation exists:**
- `y/prices/dex/uniswap/v3.py`, lines in `get_price()`:
  ```python
  paths = [(token, fee, usdc.address) for fee in self.fee_tiers]
  if token != weth:
      paths += [(token, fee, weth.address, self.fee_tiers[0], usdc.address) for fee in self.fee_tiers]
  ```

### The Deepest Pool Problem for V2

V2's `get_path_to_stables()` only follows the **single deepest pool**. If the deepest pool for MIC is a garbage pool with bad reserves (e.g., MIC/RANDOM_TOKEN), it will try to route through that instead of the viable MIC/USDT pool.

**Key file**: `y/prices/dex/uniswap/v2.py`, method `get_path_to_stables()`

---

## Recommendations for Adding Better Multi-Hop Support

### Option A: Improve V3 Path Generation (Easiest, in ypricemagic library)

**File**: `y/prices/dex/uniswap/v3.py`, method `UniswapV3.get_price()`

Add more intermediary tokens to the path list:

```python
# Current:
paths = [(token, fee, usdc.address) for fee in self.fee_tiers]
if token != weth:
    paths += [(token, fee, weth.address, self.fee_tiers[0], usdc.address) for fee in self.fee_tiers]

# Proposed: add USDT, DAI, WBTC as intermediaries
ROUTING_TOKENS = [weth.address, usdt.address, dai.address, wbtc.address]
paths = [(token, fee, usdc.address) for fee in self.fee_tiers]
for intermediate in ROUTING_TOKENS:
    if token != intermediate:
        paths += [(token, fee, intermediate, self.fee_tiers[0], usdc.address) for fee in self.fee_tiers]
```

**Pros**: Simple, uses V3's native multi-hop quoter, stays in the library
**Cons**: More RPC calls per price lookup (but they run in parallel via `igather`)

### Option B: Improve V2 `get_path_to_stables()` to Try Multiple Pools

Instead of only following the deepest pool, try the top N pools and return the path that gives the best quote.

### Option C: Add Multi-Hop at Server Level (in ypricemagic-server)

Not recommended — the routing logic belongs in the library where it has access to pool data and on-chain quoting.

### Best Place to Add Support

**In the library** (`y/prices/dex/uniswap/v3.py` and `y/prices/dex/uniswap/v2.py`), specifically:
1. **V3**: Expand the path list in `get_price()` to include more intermediary tokens
2. **V2**: The existing recursive logic is already fairly robust; the main improvement would be trying multiple candidate pools instead of just the deepest one

---

## Key Code Snippets

### V2 get_path_to_stables (recursive multi-hop builder)
```python
# y/prices/dex/uniswap/v2.py
async def get_path_to_stables(self, token, block, _loop_count=0, _ignore_pools=()):
    if _loop_count > 10:
        raise CantFindSwapPath
    path = [token_address]
    deepest_pool = await self.deepest_pool(token_address, block, _ignore_pools)
    if deepest_pool:
        paired_with = await deepest_pool.get_token_out(token_address)
        deepest_stable_pool = await self.deepest_stable_pool(token_address, block, ...)
        if deepest_stable_pool and deepest_pool == deepest_stable_pool:
            path.append(await deepest_stable_pool.get_token_out(token_address))
            return path  # e.g., [MIC, USDT]
        # Recurse through the paired token
        path.extend(await self.get_path_to_stables(paired_with, block, _loop_count+1, ...))
    return path  # e.g., [MIC, WETH, USDC]
```

### V2 deepest pool fallback (indirect pricing via recursive magic.get_price)
```python
# y/prices/dex/uniswap/v2.py, in get_price()
if path is None and (deepest_pool := await self.deepest_pool(token_in, block, ...)):
    paired_with = await deepest_pool.get_token_out(token_in)
    path = [token_in, paired_with]
    quote = await self.get_quote(amount_in, path, block=block)
    paired_with_price = await magic.get_price(paired_with, block, fail_to_None=True, ...)
    if paired_with_price:
        return UsdPrice(amount_out * Decimal(paired_with_price) / _amount)
```

### V3 hardcoded paths (the limitation)
```python
# y/prices/dex/uniswap/v3.py, in get_price()
paths = [(token, fee, usdc.address) for fee in self.fee_tiers]
if token != weth:
    paths += [(token, fee, weth.address, self.fee_tiers[0], usdc.address)
              for fee in self.fee_tiers]
# Only USDC and WETH→USDC as targets. No USDT, DAI, WBTC intermediaries.
```

### V2 smol brain path selector
```python
# y/prices/dex/uniswap/v2.py
def _smol_brain_path_selector(self, token_in, token_out, paired_against):
    # Default: route through WETH
    path = [token_in, WRAPPED_GAS_COIN, token_out]
```
