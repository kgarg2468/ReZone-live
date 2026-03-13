"""Simple in-memory TTL cache used by live data providers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, _CacheEntry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() >= entry.expires_at:
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._store[key] = _CacheEntry(
            value=value,
            expires_at=time.time() + self.ttl_seconds,
        )

