import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

import diskcache

logger = logging.getLogger("ypricemagic-api")

CACHE_DIR = os.environ.get("CACHE_DIR", "/data/cache")

_cache: Optional[diskcache.Cache] = None
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


def get_cached_price(token: str, block: int) -> Optional[dict]:
    try:
        cache = get_cache()
        key = make_key(token, block)
        entry = cache.get(key)
        if entry is not None and isinstance(entry, dict) and "price" in entry:
            return entry
        return None
    except Exception as e:
        logger.warning("Cache read failed, proceeding without cache: %s", e)
        return None


def set_cached_price(token: str, block: int, price: float) -> None:
    try:
        cache = get_cache()
        key = make_key(token, block)
        entry = {
            "price": price,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        cache.set(key, entry)
    except Exception as e:
        logger.warning("Cache write failed (price still returned to caller): %s", e)
