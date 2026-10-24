"""In-memory sliding-window rate limiter.

State lives in the process, so limits apply per worker. Run a single worker, or replace this
with a shared store before scaling out.
"""

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> float | None:
        """Record a hit. Returns None if allowed, otherwise seconds until the next allowed hit."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + window_seconds - now
            hits.append(now)
            return None

    def count(self, key: str, window_seconds: int) -> int:
        """Hits inside the window, without recording a new one."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if not hits:
                return 0
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            return len(hits)

    def record(self, key: str) -> None:
        with self._lock:
            self._hits[key].append(time.monotonic())

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, limit: int, window_seconds: int):
    """FastAPI dependency limiting requests per client IP for one bucket."""

    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        retry_after = limiter.hit(f"{bucket}:ip:{client_ip(request)}", limit, window_seconds)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
                headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )

    return dependency


def is_limited_for_key(bucket: str, key: str, limit: int, window_seconds: int) -> bool:
    """Check a per-key limit without counting this request (pair with record_for_key)."""
    if not get_settings().rate_limit_enabled:
        return False
    return limiter.count(f"{bucket}:key:{key}", window_seconds) >= limit


def record_for_key(bucket: str, key: str) -> None:
    if get_settings().rate_limit_enabled:
        limiter.record(f"{bucket}:key:{key}")


def allow_for_key(bucket: str, key: str, limit: int, window_seconds: int) -> bool:
    """Silent per-key limit (e.g. per email address) for endpoints that must not reveal the outcome."""
    if not get_settings().rate_limit_enabled:
        return True
    return limiter.hit(f"{bucket}:key:{key}", limit, window_seconds) is None
