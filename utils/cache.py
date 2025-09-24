import time
from typing import Any, Dict, Optional

# Simple in-memory cache for demonstration (replace with Redis in prod)
_cache: Dict[str, tuple] = {}

def set_cache(key: str, value: Any, ttl: int = 60):
    _cache[key] = (value, time.time() + ttl)

def get_cache(key: str) -> Optional[Any]:
    v = _cache.get(key)
    if not v:
        return None
    value, expires = v
    if time.time() > expires:
        _cache.pop(key, None)
        return None
    return value

def invalidate_cache(key: str):
    _cache.pop(key, None)
