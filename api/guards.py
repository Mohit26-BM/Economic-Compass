"""Small shared helpers for the API: client keys, rate limiting, caching, safe errors."""

import os
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from fastapi import HTTPException, Request
from loguru import logger

# The only series the platform ingests. Anything else is a 404, not a database query.
KNOWN_SERIES = {
    "GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "T10Y2Y", "HOUST", "RSXFS", "USREC", "PAYEMS",
}
FORECAST_SERIES = {"GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "T10Y2Y", "HOUST", "RSXFS"}


def client_key(request: Request) -> str:
    """
    Address used for rate limiting. X-Forwarded-For is only believed when TRUSTED_PROXY_HOPS says
    how many proxies sit in front of the app (Render counts as 1). With 0, a visitor could invent
    a new address on every request and never be limited.
    """
    hops = int(os.environ.get("TRUSTED_PROXY_HOPS", "0") or 0)
    if hops > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Sliding window, in memory (one instance per process)."""

    def __init__(self, limit: int, window_seconds: float = 60.0, max_keys: int = 5000):
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > self.max_keys:  # never let a flood of fake keys grow memory without bound
                self._hits = defaultdict(
                    deque, {k: v for k, v in self._hits.items() if v and now - v[-1] < self.window}
                )
            q = self._hits[key]
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def retry_after(self, key: str, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        q = self._hits.get(key)
        if not q:
            return 1
        return max(1, int(self.window - (now - q[0])) + 1)


def rate_limit(limiter: RateLimiter):
    """FastAPI dependency: 429 with Retry-After when a visitor goes over the limit."""

    def dependency(request: Request) -> None:
        key = client_key(request)
        if not limiter.allow(key):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(limiter.retry_after(key))},
            )

    return dependency


# 30 scenario runs a minute and 120 other analysis reads a minute per visitor (override with env).
simulate_limiter = RateLimiter(int(os.environ.get("SIMULATE_RATE_PER_MIN", "30") or 30))
read_limiter = RateLimiter(int(os.environ.get("READ_RATE_PER_MIN", "120") or 120))


from ml.cache import cached_on_files  # noqa: E402,F401  (re-exported for the routers)


def public_error(exc: Exception, what: str) -> HTTPException:
    """
    Turn an exception into a response that is safe to show. Our own FileNotFoundError and
    ValueError messages are written for users and kept; anything else is logged in full and
    replaced by a generic message, so paths, SQL and library internals never reach the client.
    """
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail="That model or result has not been generated yet.")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail="Not enough data to compute this.")
    logger.exception(f"{what} failed")
    return HTTPException(status_code=500, detail=f"{what} is unavailable right now.")
