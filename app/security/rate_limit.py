"""In-memory sliding-window rate limiter (no extra dependencies)."""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, limit: int, window_sec: int) -> None:
        self.limit = max(1, int(limit))
        self.window_sec = max(1, int(window_sec))
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            cutoff = now - self.window_sec
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry = int(max(1, self.window_sec - (now - bucket[0])))
                return False, 0, retry
            bucket.append(now)
            remaining = self.limit - len(bucket)
            return True, remaining, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
