from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cache import get_cached_price, make_key, set_cached_price


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path) -> Generator[None, None, None]:
    """Each test gets a fresh cache in a temp directory."""
    with patch("src.cache.CACHE_DIR", str(tmp_path)), patch("src.cache._cache", None):
        yield


class TestMakeKey:
    def test_lowercases_token(self) -> None:
        assert make_key("0xABCDEF", 100) == "0xabcdef:100"

    def test_includes_block(self) -> None:
        assert make_key("0xabc", 99999) == "0xabc:99999"


class TestGetCachedPrice:
    def test_returns_none_when_missing(self) -> None:
        assert get_cached_price("0xtoken", 1) is None

    def test_returns_entry_after_set(self) -> None:
        set_cached_price("0xToken", 500, 1.23)
        result = get_cached_price("0xToken", 500)
        assert result is not None
        assert result["price"] == 1.23

    def test_cache_key_is_case_insensitive(self) -> None:
        set_cached_price("0xABCD", 1, 9.99)
        assert get_cached_price("0xabcd", 1) is not None
        assert get_cached_price("0xABCD", 1) is not None

    def test_different_blocks_are_separate_entries(self) -> None:
        set_cached_price("0xtoken", 1, 1.0)
        set_cached_price("0xtoken", 2, 2.0)
        r1 = get_cached_price("0xtoken", 1)
        r2 = get_cached_price("0xtoken", 2)
        assert r1 is not None and r1["price"] == 1.0
        assert r2 is not None and r2["price"] == 2.0

    def test_returns_none_on_cache_read_error(self) -> None:
        with patch("src.cache.get_cache", side_effect=RuntimeError("disk full")):
            assert get_cached_price("0xtoken", 1) is None


class TestSetCachedPrice:
    def test_stored_entry_has_cached_at(self) -> None:
        set_cached_price("0xtoken", 1, 42.0)
        result = get_cached_price("0xtoken", 1)
        assert result is not None
        assert "cached_at" in result

    def test_write_error_does_not_raise(self) -> None:
        with patch("src.cache.get_cache", side_effect=RuntimeError("disk full")):
            set_cached_price("0xtoken", 1, 1.0)  # must not raise
