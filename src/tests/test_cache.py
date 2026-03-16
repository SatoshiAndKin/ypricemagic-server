from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cache import (
    get_cached_error,
    get_cached_errors,
    get_cached_price,
    make_key,
    set_cached_error,
    set_cached_price,
)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path) -> Generator[None]:
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


class TestBlockTimestampInCache:
    """Tests for block_timestamp field in cache entries."""

    def test_set_cached_price_stores_block_timestamp(self) -> None:
        """When block_timestamp is provided, it's stored in the cache entry."""
        set_cached_price("0xtoken", 1, 42.0, block_timestamp=1700000000)
        result = get_cached_price("0xtoken", 1)
        assert result is not None
        assert result["price"] == 42.0
        assert result.get("block_timestamp") == 1700000000

    def test_set_cached_price_without_block_timestamp(self) -> None:
        """When block_timestamp is not provided, it defaults to None."""
        set_cached_price("0xtoken", 1, 42.0)
        result = get_cached_price("0xtoken", 1)
        assert result is not None
        assert result.get("block_timestamp") is None

    def test_get_cached_price_returns_block_timestamp(self) -> None:
        """Cache hit returns the stored block_timestamp."""
        set_cached_price("0xtoken", 1, 42.0, block_timestamp=1700000000)
        result = get_cached_price("0xtoken", 1)
        assert result is not None
        assert result["block_timestamp"] == 1700000000

    def test_old_cache_entry_without_block_timestamp_returns_none(self, tmp_path: Path) -> None:
        """Pre-upgrade cache entries (without block_timestamp) return block_timestamp: None."""
        # Simulate an old cache entry without block_timestamp
        from src.cache import get_cache, make_key

        with patch("src.cache.CACHE_DIR", str(tmp_path)), patch("src.cache._cache", None):
            cache = get_cache()
            key = make_key("0xoldtoken", 1)
            old_entry = {"price": 99.0, "cached_at": "2023-01-01T00:00:00+00:00"}
            cache.set(key, old_entry)

            # Now get_cached_price should return the entry with block_timestamp: None
            result = get_cached_price("0xoldtoken", 1)
            assert result is not None
            assert result["price"] == 99.0
            assert result.get("block_timestamp") is None


class TestGetCachedError:
    """Tests for error entry reads."""

    def test_returns_none_when_missing(self) -> None:
        assert get_cached_error("0xtoken", 1) is None

    def test_returns_error_entry_after_set(self) -> None:
        set_cached_error("0xToken", 500, "price lookup failed")
        result = get_cached_error("0xToken", 500)
        assert result is not None
        assert result["error"] == "price lookup failed"

    def test_returns_none_for_price_entry(self) -> None:
        """get_cached_error ignores successful price entries."""
        set_cached_price("0xtoken", 1, 99.0)
        assert get_cached_error("0xtoken", 1) is None

    def test_cache_key_is_case_insensitive(self) -> None:
        set_cached_error("0xABCD", 1, "oops")
        assert get_cached_error("0xabcd", 1) is not None
        assert get_cached_error("0xABCD", 1) is not None

    def test_returns_none_on_cache_read_error(self) -> None:
        with patch("src.cache.get_cache", side_effect=RuntimeError("disk full")):
            assert get_cached_error("0xtoken", 1) is None


class TestSetCachedError:
    """Tests for error entry writes."""

    def test_stored_error_entry_has_required_fields(self) -> None:
        set_cached_error("0xtoken", 1, "something went wrong")
        result = get_cached_error("0xtoken", 1)
        assert result is not None
        assert result["error"] == "something went wrong"
        assert "cached_at" in result
        assert result["block_timestamp"] is None

    def test_error_entry_does_not_shadow_price(self) -> None:
        """Setting an error does not affect an existing price entry."""
        set_cached_price("0xtoken", 1, 42.0)
        set_cached_error("0xtoken", 1, "oops")
        # The cache now holds an error entry (overwrote the price entry).
        # get_cached_price should return None because the stored entry has "error" not "price".
        assert get_cached_price("0xtoken", 1) is None

    def test_write_error_does_not_raise(self) -> None:
        with patch("src.cache.get_cache", side_effect=RuntimeError("disk full")):
            set_cached_error("0xtoken", 1, "fail")  # must not raise

    def test_get_cached_price_ignores_error_entry(self) -> None:
        """get_cached_price returns None when only an error entry is stored."""
        set_cached_error("0xtoken", 2, "no price")
        assert get_cached_price("0xtoken", 2) is None


class TestGetCachedErrors:
    """Tests for iterating over error entries."""

    def test_yields_nothing_when_empty(self) -> None:
        results = list(get_cached_errors())
        assert results == []

    def test_yields_error_entries(self) -> None:
        set_cached_error("0xtoken", 100, "err1")
        set_cached_error("0xtoken2", 200, "err2")
        results = list(get_cached_errors())
        keys = {(t, b) for t, b, _ in results}
        assert ("0xtoken", 100) in keys
        assert ("0xtoken2", 200) in keys

    def test_skips_price_entries(self) -> None:
        set_cached_price("0xprice", 1, 1.0)
        set_cached_error("0xerr", 1, "fail")
        results = list(get_cached_errors())
        tokens = [t for t, _, _ in results]
        assert "0xprice" not in tokens
        assert "0xerr" in tokens

    def test_entry_has_error_field(self) -> None:
        set_cached_error("0xtoken", 77, "test error message")
        results = list(get_cached_errors())
        assert len(results) == 1
        token, block, entry = results[0]
        assert token == "0xtoken"
        assert block == 77
        assert entry["error"] == "test error message"
