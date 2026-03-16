import os
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import cast

import diskcache

from src.logger import get_logger

logger = get_logger("cache")

CACHE_DIR = os.environ.get("CACHE_DIR", "/data/cache")

# TTL for error cache entries (1 hour). After expiry the entry is evicted and
# the next request will re-attempt the real price lookup.
ERROR_CACHE_TTL = int(os.environ.get("ERROR_CACHE_TTL", "3600"))

_cache: diskcache.Cache | None = None
_lock = threading.Lock()


def get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                os.makedirs(CACHE_DIR, exist_ok=True)
                _cache = diskcache.Cache(CACHE_DIR)
    return _cache


def close_cache() -> None:
    global _cache
    with _lock:
        if _cache is not None:
            _cache.close()
            _cache = None


def make_key(token: str, block: int) -> str:
    return f"{token.lower()}:{block}"


def get_cached_price(token: str, block: int) -> dict[str, object] | None:
    """Return a cached price entry, or None if not found.

    Returns only *successful* price entries (those with a ``"price"`` key).
    Error entries are ignored here — use :func:`get_cached_error` to retrieve them.
    """
    try:
        cache = get_cache()
        key = make_key(token, block)
        entry = cache.get(key)
        if entry is not None and isinstance(entry, dict) and "price" in entry:
            # Ensure block_timestamp is present (backward compat with old entries)
            if "block_timestamp" not in entry:
                entry["block_timestamp"] = None
            return cast(dict[str, object], entry)
        return None
    except Exception as e:
        logger.warning("cache_read_failed", error=str(e))
        return None


def get_cached_error(token: str, block: int) -> dict[str, object] | None:
    """Return a cached error entry, or None if not found.

    Error entries have an ``"error"`` key and a TTL set on them so they
    expire automatically and get retried.
    """
    try:
        cache = get_cache()
        key = make_key(token, block)
        entry = cache.get(key)
        if entry is not None and isinstance(entry, dict) and "error" in entry:
            return cast(dict[str, object], entry)
        return None
    except Exception as e:
        logger.warning("cache_read_error_entry_failed", error=str(e))
        return None


def set_cached_price(
    token: str, block: int, price: float, block_timestamp: int | None = None
) -> None:
    try:
        cache = get_cache()
        key = make_key(token, block)
        entry: dict[str, object] = {
            "price": price,
            "cached_at": datetime.now(UTC).isoformat(),
            "block_timestamp": block_timestamp,
        }
        cache.set(key, entry)
    except Exception as e:
        logger.warning("cache_write_failed", error=str(e))


def set_cached_error(token: str, block: int, error: str) -> None:
    """Cache a failed price-lookup result with a TTL so it can be retried later.

    The entry schema is::

        {
            "error": "<human-readable error string>",
            "cached_at": "<ISO-8601 UTC timestamp>",
            "block_timestamp": None,
        }

    The entry expires after :data:`ERROR_CACHE_TTL` seconds.  On expiry,
    :func:`get_cached_error` returns ``None`` and the next request will
    attempt a real lookup again.
    """
    try:
        cache = get_cache()
        key = make_key(token, block)
        entry: dict[str, object] = {
            "error": error,
            "cached_at": datetime.now(UTC).isoformat(),
            "block_timestamp": None,
        }
        cache.set(key, entry, expire=ERROR_CACHE_TTL)
    except Exception as e:
        logger.warning("cache_write_error_failed", error=str(e))


def get_cached_errors() -> Iterator[tuple[str, int, dict[str, object]]]:
    """Iterate over all unexpired error entries in the cache.

    Yields ``(token, block, entry)`` tuples where:

    - ``token`` is the checksummed address (lowercased, as stored).
    - ``block`` is the block number.
    - ``entry`` is the dict containing ``"error"``, ``"cached_at"``, and
      ``"block_timestamp"``.

    Only yields entries that have an ``"error"`` key (i.e. error entries,
    not successful price entries).
    """
    try:
        cache = get_cache()
        for key in cache:
            try:
                entry = cache.get(key)
                if entry is None or not isinstance(entry, dict) or "error" not in entry:
                    continue
                # Key format: "<token_lower>:<block>"
                parts = str(key).rsplit(":", 1)
                if len(parts) != 2:
                    continue
                token_lower, block_str = parts
                block = int(block_str)
                yield token_lower, block, cast(dict[str, object], entry)
            except Exception as e:
                logger.warning("cache_iter_entry_failed", key=key, error=str(e))
    except Exception as e:
        logger.warning("cache_iter_failed", error=str(e))
