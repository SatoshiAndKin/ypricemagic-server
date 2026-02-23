import os
from datetime import datetime, timezone
from typing import Optional

import diskcache

CACHE_DIR = os.environ.get("CACHE_DIR", "/data/cache")

_cache: Optional[diskcache.Cache] = None


def get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        os.makedirs(CACHE_DIR, exist_ok=True)
        _cache = diskcache.Cache(CACHE_DIR)
    return _cache


def make_key(token: str, block: int) -> str:
    return f"{token.lower()}:{block}"


def get_cached_price(token: str, block: int) -> Optional[dict]:
    cache = get_cache()
    key = make_key(token, block)
    return cache.get(key)


def set_cached_price(token: str, block: int, price: float) -> dict:
    cache = get_cache()
    key = make_key(token, block)
    entry = {
        "price": price,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    cache.set(key, entry)
    return entry
