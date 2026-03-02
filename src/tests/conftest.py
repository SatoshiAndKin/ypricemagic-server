"""Pytest configuration and fixtures for server tests."""

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_y_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the y module to avoid brownie network requirement during tests."""
    mock_y: Any = MagicMock()
    mock_y.get_price = MagicMock()
    monkeypatch.setitem(sys.modules, "y", mock_y)
