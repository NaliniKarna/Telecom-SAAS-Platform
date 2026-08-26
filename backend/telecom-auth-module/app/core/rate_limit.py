"""In-process rate limiting and lockout for API-key authentication.

No Redis (or any shared cache) exists in this project. See
IMPLEMENTATION-REPORT.md for the full reasoning; short version: introducing
a new infrastructure dependency (Redis) for a not-yet-load-tested feature
would be scope creep, so this is deliberately the smallest correct
implementation for a SINGLE-PROCESS deployment.

Consequences of that choice (know these before relying on it):
  - State lives in a plain dict guarded by an asyncio.Lock, in memory, for
    the life of the process. It resets on every restart/deploy.
  - It is NOT shared across multiple uvicorn workers or multiple
    replicas/pods. Running with `--workers 4` silently gives you 4x the
    configured limit, split unpredictably across whichever worker handles
    each request. Same problem across horizontally-scaled containers.

If/when this app runs as more than one process, replace both classes below
with a Redis-backed equivalent (INCR + EXPIRE is a direct drop-in for
SlidingWindowLimiter; a SET with TTL is a direct drop-in for the lockout
half of LockoutTracker) — the call sites in app/api/v1/deps.py don't need to
change, only what's injected there.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Allows up to `limit` events per `window_seconds` rolling window, per key."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, *, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        async with self._lock:
            q = self._hits[key]
            cutoff = now - window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


class LockoutTracker:
    """Escalates repeated failures into a hard lockout.

    Once `limit` failures land within `window_seconds` for a key, that key
    is blocked for `lockout_seconds` — regardless of whether individual
    failures would still fit under a simple rolling-window count. This is
    the same shape as the existing per-user login lockout
    (User.failed_login_count / settings.MAX_FAILED_LOGINS), applied here to
    IPs instead of user rows since there's no persistent entity to attach a
    counter column to.
    """

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def is_locked(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            until = self._locked_until.get(key)
            if until is None:
                return False
            if now >= until:
                del self._locked_until[key]
                return False
            return True

    async def register_failure(
        self, key: str, *, limit: int, window_seconds: float, lockout_seconds: float,
    ) -> bool:
        """Record one failure. Returns True if this failure just triggered a
        new lockout (i.e. the caller should audit/log it)."""
        now = time.monotonic()
        async with self._lock:
            q = self._failures[key]
            cutoff = now - window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            q.append(now)
            if len(q) >= limit:
                self._locked_until[key] = now + lockout_seconds
                q.clear()
                return True
            return False

    async def register_success(self, key: str) -> None:
        async with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)


# Process-wide singletons, imported by app.api.v1.deps. Two independent
# trackers because they gate different things:
#   - ip_auth_lockout: guessing/probing keys (keyed by caller IP)
#   - api_key_request_limiter: abuse via a VALID key (keyed by key id)
ip_auth_lockout = LockoutTracker()
api_key_request_limiter = SlidingWindowLimiter()