from __future__ import annotations

import time
from collections.abc import Callable
from threading import RLock
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int = 45) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[tuple[Any, ...], tuple[float, Any]] = {}
        self._lock = RLock()

    def get_or_set(self, key: tuple[Any, ...], loader: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            expires_at, value = self._items.get(key, (0.0, None))
            if expires_at > now:
                return value
        value = loader()
        with self._lock:
            self._items[key] = (now + self.ttl_seconds, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


dashboard_cache = TTLCache(ttl_seconds=45)
product_cache = TTLCache(ttl_seconds=45)
source_cache = TTLCache(ttl_seconds=45)
