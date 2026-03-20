"""Pytest configuration and fixtures for server tests."""

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Minimal valid tokenlist fixture for tests
# This is used when the full Uniswap tokenlist is not present (gitignored)
MINIMAL_TOKENLIST = {
    "name": "Test Tokenlist",
    "version": {"major": 1, "minor": 0, "patch": 0},
    "tokens": [
        {
            "chainId": 1,
            "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
            "name": "Dai Stablecoin",
            "symbol": "DAI",
            "decimals": 18,
        },
        {
            "chainId": 1,
            "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "name": "USD Coin",
            "symbol": "USDC",
            "decimals": 6,
        },
        {
            "chainId": 42161,
            "address": "0xDA10009cBd5D07dd0CeCc6364F8F8D61F49D8419",
            "name": "Dai Stablecoin",
            "symbol": "DAI",
            "decimals": 18,
        },
    ],
}


@pytest.fixture(autouse=True)
def ensure_tokenlist_fixture() -> None:
    """Ensure a valid tokenlist exists for static file tests.

    The uniswap-default.json file is gitignored (to avoid Droid-Shield false positives
    on addresses), so CI checkouts won't have it. This fixture creates a minimal valid
    tokenlist before tests run if the file doesn't exist.

    Production Docker builds download the full Uniswap tokenlist during image build.
    """
    tokenlist_path = (
        Path(__file__).parent.parent.parent / "static" / "tokenlists" / "uniswap-default.json"
    )
    if not tokenlist_path.exists():
        tokenlist_path.parent.mkdir(parents=True, exist_ok=True)
        tokenlist_path.write_text(json.dumps(MINIMAL_TOKENLIST, indent=2))


@pytest.fixture(autouse=True)
def mock_y_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the y module to avoid brownie network requirement during tests."""

    # Create a NodeNotSynced exception class matching ypricemagic's name
    class NodeNotSynced(Exception):  # noqa: N818
        pass

    # Create mock y.time submodule
    mock_y_time: Any = MagicMock()
    mock_y_time.check_node_async = MagicMock()

    # Create mock y.exceptions submodule
    mock_y_exceptions: Any = MagicMock()
    mock_y_exceptions.NodeNotSynced = NodeNotSynced

    # Create mock y.classes.common submodule
    mock_y_classes_common: Any = MagicMock()
    mock_y_classes: Any = MagicMock()
    mock_y_classes.common = mock_y_classes_common

    # Create mock y.prices subtree for Curve and Uniswap pre-warming
    mock_y_prices: Any = MagicMock()
    mock_y_prices_stable_swap: Any = MagicMock()
    mock_y_prices_stable_swap_curve: Any = MagicMock()
    mock_y_prices_stable_swap_curve.curve = None  # No Curve registry by default
    mock_y_prices_stable_swap.curve = mock_y_prices_stable_swap_curve
    mock_y_prices.stable_swap = mock_y_prices_stable_swap

    mock_y_prices_dex: Any = MagicMock()
    mock_y_prices_dex_uniswap: Any = MagicMock()
    mock_uniswap_multiplexer: Any = MagicMock()
    mock_uniswap_multiplexer.v2_routers = {}
    mock_uniswap_multiplexer.v3 = None
    mock_uniswap_multiplexer.v3_forks = []
    mock_y_prices_dex_uniswap.uniswap_multiplexer = mock_uniswap_multiplexer
    mock_y_prices_dex.uniswap = mock_y_prices_dex_uniswap
    mock_y_prices.dex = mock_y_prices_dex

    # Create main mock y module
    mock_y: Any = MagicMock()
    mock_y.get_price = MagicMock()
    mock_y.time = mock_y_time
    mock_y.exceptions = mock_y_exceptions
    mock_y.classes = mock_y_classes
    mock_y.prices = mock_y_prices

    # Install mocks
    monkeypatch.setitem(sys.modules, "y", mock_y)
    monkeypatch.setitem(sys.modules, "y.time", mock_y_time)
    monkeypatch.setitem(sys.modules, "y.exceptions", mock_y_exceptions)
    monkeypatch.setitem(sys.modules, "y.classes", mock_y_classes)
    monkeypatch.setitem(sys.modules, "y.classes.common", mock_y_classes_common)
    monkeypatch.setitem(sys.modules, "y.prices", mock_y_prices)
    monkeypatch.setitem(sys.modules, "y.prices.stable_swap", mock_y_prices_stable_swap)
    monkeypatch.setitem(sys.modules, "y.prices.stable_swap.curve", mock_y_prices_stable_swap_curve)
    monkeypatch.setitem(sys.modules, "y.prices.dex", mock_y_prices_dex)
    monkeypatch.setitem(sys.modules, "y.prices.dex.uniswap", mock_y_prices_dex_uniswap)
    monkeypatch.setitem(sys.modules, "y.prices.dex.uniswap.uniswap", mock_y_prices_dex_uniswap)

    # Mock brownie modules needed by lifespan tests
    mock_brownie: Any = MagicMock()
    mock_brownie_network: Any = MagicMock()
    mock_brownie_network.is_connected.return_value = True
    mock_brownie.network = mock_brownie_network
    mock_brownie_chain: Any = MagicMock()
    mock_brownie_chain.id = 1
    mock_brownie_chain.height = 19000000
    mock_brownie.chain = mock_brownie_chain
    monkeypatch.setitem(sys.modules, "brownie", mock_brownie)

    # Mock dank_mids modules needed by lifespan
    mock_dank_mids: Any = MagicMock()
    mock_dank_mids_helpers: Any = MagicMock()
    mock_dank_mids_helpers.setup_dank_w3_from_sync = MagicMock()
    mock_dank_mids.helpers = mock_dank_mids_helpers
    monkeypatch.setitem(sys.modules, "dank_mids", mock_dank_mids)
    monkeypatch.setitem(sys.modules, "dank_mids.helpers", mock_dank_mids_helpers)
    mock_dank_mids_helpers_helpers: Any = MagicMock()
    monkeypatch.setitem(sys.modules, "dank_mids.helpers._helpers", mock_dank_mids_helpers_helpers)

    # Mock web3.middleware for lifespan (geth_poa_middleware)
    mock_web3_middleware: Any = MagicMock()
    monkeypatch.setitem(sys.modules, "web3.middleware", mock_web3_middleware)
