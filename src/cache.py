import os
import threading
from datetime import UTC, datetime
from typing import cast

import diskcache

from src.logger import get_logger

logger = get_logger("cache")

CACHE_DIR = os.environ.get("CACHE_DIR", "/data/cache")

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


def make_key(token: str, block: int) -> str:
    return f"{token.lower()}:{block}"


def get_cached_price(token: str, block: int) -> dict[str, object] | None:
    try:
        cache = get_cache()
        key = make_key(token, block)
        entry = cache.get(key)
        if entry is not None and isinstance(entry, dict) and "price" in entry:
            return cast(dict[str, object], entry)
        return None
    except Exception as e:
        logger.warning("cache_read_failed", error=str(e))
        return None


def set_cached_price(token: str, block: int, price: float) -> None:
    try:
        cache = get_cache()
        key = make_key(token, block)
        entry: dict[str, object] = {
            "price": price,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        cache.set(key, entry)
    except Exception as e:
        logger.warning("cache_write_failed", error=str(e))
