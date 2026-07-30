"""A small in-process rate limiter for the agent endpoints.

Deliberately simple: a fixed-window counter in a dict. There is no Redis in this backend,
so the counter is **per process** — behind N Cloud Run instances the effective ceiling is
`limit × instances`. That is fine for its purpose, which is to stop one misbehaving or
looping endpoint from hammering the database, not to enforce an exact global quota.

Default mode is **log-only**: limits are counted and breaches are logged, but nothing is
rejected. Watch the logs against real fleet traffic first, then switch enforcement on —
a too-tight limit here would drop genuine heartbeats and show devices as offline.
"""
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("astra.rate_limit")

# Keys idle for this long are dropped, so the dict tracks only active devices.
_IDLE_EVICT_SECONDS = 600


@dataclass
class _Window:
    started_at: float
    count: int = 0


@dataclass
class FixedWindowLimiter:
    limit: int
    window_seconds: int
    _windows: dict[str, _Window] = field(default_factory=dict)
    _last_sweep: float = 0.0

    def check(self, key: str) -> tuple[bool, int]:
        """Record a hit for `key`. Returns (allowed, count_in_window).

        `allowed` is False once the count exceeds the limit; callers decide whether to
        act on it. Runs entirely synchronously — no awaits — so on an asyncio event loop
        the read-modify-write is atomic without a lock.
        """
        now = time.monotonic()
        self._sweep(now)

        window = self._windows.get(key)
        if window is None or now - window.started_at >= self.window_seconds:
            window = _Window(started_at=now)
            self._windows[key] = window

        window.count += 1
        return window.count <= self.limit, window.count

    def _sweep(self, now: float) -> None:
        """Evict idle keys, at most once per window, so the dict can't grow unbounded."""
        if now - self._last_sweep < self.window_seconds:
            return
        self._last_sweep = now
        cutoff = now - _IDLE_EVICT_SECONDS
        for key in [k for k, w in self._windows.items() if w.started_at < cutoff]:
            del self._windows[key]

    def reset(self) -> None:
        self._windows.clear()
        self._last_sweep = 0.0


class RateLimitExceeded(Exception):
    """Raised only when enforcement is enabled."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


def apply_limit(
    limiter: FixedWindowLimiter, key: str, *, enforce: bool, label: str
) -> None:
    """Count a hit and, when enforcing, raise once the key is over its limit."""
    allowed, count = limiter.check(key)
    if allowed:
        return
    logger.warning(
        "rate limit %s: %s made %d requests in %ds (limit %d)",
        "EXCEEDED (rejected)" if enforce else "exceeded (log-only, allowed)",
        f"{label}={key}",
        count,
        limiter.window_seconds,
        limiter.limit,
    )
    if enforce:
        raise RateLimitExceeded(retry_after=limiter.window_seconds)
