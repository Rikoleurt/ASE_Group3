"""Simple in-process rate limits (#98): failed logins, comments and uploads.

A sliding window per key: at most `limit` events in `seconds`. The counts live in this
process's memory, so they reset on restart and are per worker; that is enough to stop a
script hammering one server, and a deployment with several workers can put a shared limit
(e.g. at the reverse proxy) in front.
"""
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException


class RateLimit:
    def __init__(self, limit: int, seconds: float) -> None:
        self.limit = limit
        self.seconds = seconds
        self._events: dict[str, deque] = {}
        self._lock = Lock()

    def _recent(self, key: str, now: float) -> deque:
        events = self._events.setdefault(key, deque())
        while events and events[0] <= now - self.seconds:
            events.popleft()
        return events

    def blocked_for(self, key: str) -> float:
        """Seconds until `key` may act again; 0 when it may act now."""
        now = time.monotonic()
        with self._lock:
            events = self._recent(key, now)
            if len(events) < self.limit:
                return 0.0
            return max(events[0] + self.seconds - now, 0.0)

    def record(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._recent(key, now).append(now)
            if len(self._events) > 50_000:  # forget idle keys rather than grow without bound
                for idle in [k for k, v in self._events.items() if not v]:
                    del self._events[idle]

    def check(self, key: str, message: str) -> None:
        """Raise 429 with Retry-After when `key` is over the limit."""
        wait = self.blocked_for(key)
        if wait:
            raise HTTPException(429, message, headers={"Retry-After": str(int(wait) + 1)})

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


# Failed logins per account and per client address.
FAILED_LOGINS = RateLimit(limit=10, seconds=15 * 60)
# Comments on corrected copies per user.
COMMENTS = RateLimit(limit=10, seconds=60)
# Uploads per user per day (each keeps up to 10 MB on disk and runs the reader).
UPLOADS = RateLimit(limit=200, seconds=24 * 60 * 60)
# Sketch searches per client address (public; each runs the classifier on one small image).
SKETCHES = RateLimit(limit=60, seconds=60)
