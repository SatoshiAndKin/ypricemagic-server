# Testing: ypricemagic Mock Patterns

**What belongs here:** Patterns for mocking ypricemagic (`y.*`) in pytest tests.

---

## conftest.py mock_y_module: sys.modules Pattern

The `mock_y_module` fixture in `src/tests/conftest.py` mocks the `y` package and its submodules via `monkeypatch.setitem(sys.modules, ...)`. This is required because ypricemagic needs an active brownie network connection at import time.

**Key rule:** Every `y.*` submodule you import in `src/server.py` must also be registered in `sys.modules` in `mock_y_module`. If you add a new `from y.something import Foo` import to server.py, you must add corresponding entries to the fixture.

Currently mocked submodules (as of milestone `startup-and-ux`):
- `y` — main module (`get_price`, `check_bucket`, `time`, `exceptions`, `classes`, `prices`)
- `y.time` — `check_node_async`
- `y.exceptions` — `NodeNotSynced`
- `y.classes` — parent namespace, holds `.common`
- `y.classes.common` — contains `ERC20`
- `y.prices` — parent namespace for pricing modules
- `y.prices.stable_swap` — parent for Curve
- `y.prices.stable_swap.curve` — `.curve` attr (set to `None` by default)
- `y.prices.dex` — parent for DEX modules
- `y.prices.dex.uniswap` — `.uniswap_multiplexer` attr (has `v2_routers={}`, `v3=None`, `v3_forks=[]`)
- `y.prices.dex.uniswap.uniswap` — alias for the uniswap module
- `brownie` — `.network` (is_connected=True), `.chain` (id=1, height=19000000)
- `dank_mids` / `dank_mids.helpers` — `.setup_dank_w3_from_sync` (MagicMock)
- `web3.middleware` — geth_poa_middleware mock

**Example: adding a new submodule mock**

```python
# In conftest.py mock_y_module fixture:
mock_y_newmodule: Any = MagicMock()
mock_y.newmodule = mock_y_newmodule
monkeypatch.setitem(sys.modules, "y.newmodule", mock_y_newmodule)
```

---

## Mocking ERC20 Async Properties (asyncio.Future Pattern)

`ERC20` properties (`symbol`, `name`, `decimals`) are awaitable. Since `asyncio.coroutine` was removed in Python 3.11, use `asyncio.Future` with `set_result()`:

```python
import asyncio
from unittest.mock import MagicMock, patch

mock_erc20_instance = MagicMock()

symbol_fut: asyncio.Future[str] = asyncio.Future()
symbol_fut.set_result("USDC")
mock_erc20_instance.symbol = symbol_fut

name_fut: asyncio.Future[str] = asyncio.Future()
name_fut.set_result("USD Coin")
mock_erc20_instance.name = name_fut

decimals_fut: asyncio.Future[int] = asyncio.Future()
decimals_fut.set_result(6)
mock_erc20_instance.decimals = decimals_fut

mock_erc20_cls = MagicMock(return_value=mock_erc20_instance)

with patch("y.classes.common.ERC20", mock_erc20_cls):
    # ... test code
```

**Patch target:** Always patch at `y.classes.common.ERC20`, not at `src.server.ERC20`. Patching at the source is the correct approach for this import pattern.

---

## Patching y.check_bucket

```python
from unittest.mock import AsyncMock, patch

with patch("y.check_bucket", AsyncMock(return_value="stable usd")):
    # ... test code
```
