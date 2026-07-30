"""Agent rate limiting — log-only by default, enforcing when switched on."""
import pytest

from app.core.rate_limit import (
    FixedWindowLimiter,
    RateLimitExceeded,
    apply_limit,
)


def test_allows_up_to_the_limit_then_flags():
    limiter = FixedWindowLimiter(limit=3, window_seconds=60)
    assert [limiter.check("dev-1")[0] for _ in range(3)] == [True, True, True]
    allowed, count = limiter.check("dev-1")
    assert allowed is False
    assert count == 4


def test_windows_are_per_key():
    """One noisy device must not consume another device's budget."""
    limiter = FixedWindowLimiter(limit=2, window_seconds=60)
    limiter.check("dev-1")
    limiter.check("dev-1")
    assert limiter.check("dev-1")[0] is False
    assert limiter.check("dev-2")[0] is True      # unaffected


def test_window_resets_after_it_elapses(monkeypatch):
    limiter = FixedWindowLimiter(limit=1, window_seconds=60)
    clock = {"t": 1000.0}
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: clock["t"])

    assert limiter.check("dev-1")[0] is True
    assert limiter.check("dev-1")[0] is False

    clock["t"] += 61                               # next window
    assert limiter.check("dev-1")[0] is True


def test_log_only_never_raises():
    limiter = FixedWindowLimiter(limit=1, window_seconds=60)
    apply_limit(limiter, "dev-1", enforce=False, label="device")
    # Over the limit, but log-only mode must let it through.
    apply_limit(limiter, "dev-1", enforce=False, label="device")


def test_enforcing_raises_with_retry_after():
    limiter = FixedWindowLimiter(limit=1, window_seconds=45)
    apply_limit(limiter, "dev-1", enforce=True, label="device")
    with pytest.raises(RateLimitExceeded) as exc:
        apply_limit(limiter, "dev-1", enforce=True, label="device")
    assert exc.value.retry_after == 45


def test_idle_keys_are_evicted(monkeypatch):
    """The dict must not grow forever as devices come and go."""
    limiter = FixedWindowLimiter(limit=10, window_seconds=60)
    clock = {"t": 1000.0}
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: clock["t"])

    for i in range(50):
        limiter.check(f"dev-{i}")
    assert len(limiter._windows) == 50

    clock["t"] += 3600                             # well past the idle cutoff
    limiter.check("dev-fresh")                     # triggers a sweep
    assert len(limiter._windows) == 1
