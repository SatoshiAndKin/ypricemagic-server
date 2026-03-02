"""Pytest configuration and fixtures for server tests."""

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest


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

    # Create main mock y module
    mock_y: Any = MagicMock()
    mock_y.get_price = MagicMock()
    mock_y.time = mock_y_time
    mock_y.exceptions = mock_y_exceptions

    # Install mocks
    monkeypatch.setitem(sys.modules, "y", mock_y)
    monkeypatch.setitem(sys.modules, "y.time", mock_y_time)
    monkeypatch.setitem(sys.modules, "y.exceptions", mock_y_exceptions)
