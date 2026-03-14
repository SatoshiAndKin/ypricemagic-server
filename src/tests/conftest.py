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

    # Create main mock y module
    mock_y: Any = MagicMock()
    mock_y.get_price = MagicMock()
    mock_y.time = mock_y_time
    mock_y.exceptions = mock_y_exceptions
    mock_y.classes = mock_y_classes

    # Install mocks
    monkeypatch.setitem(sys.modules, "y", mock_y)
    monkeypatch.setitem(sys.modules, "y.time", mock_y_time)
    monkeypatch.setitem(sys.modules, "y.exceptions", mock_y_exceptions)
    monkeypatch.setitem(sys.modules, "y.classes", mock_y_classes)
    monkeypatch.setitem(sys.modules, "y.classes.common", mock_y_classes_common)
