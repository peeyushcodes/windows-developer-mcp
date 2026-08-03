"""
Unit tests for RateLimiter sliding window mechanism.
"""

from security.rate_limiter import RateLimiter


def test_rate_limiter_acquire():
    limiter = RateLimiter(max_calls=3, window_seconds=60)
    assert limiter.acquire() is True
    assert limiter.acquire() is True
    assert limiter.acquire() is True
    assert limiter.acquire() is False


def test_rate_limiter_stats():
    limiter = RateLimiter(max_calls=5, window_seconds=60)
    limiter.acquire()
    limiter.acquire()
    stats = limiter.get_stats()
    assert stats["max_calls"] == 5
    assert stats["active_calls_in_window"] == 2
    assert stats["remaining_calls"] == 3


def test_rate_limiter_reset():
    limiter = RateLimiter(max_calls=2, window_seconds=60)
    limiter.acquire()
    limiter.acquire()
    assert limiter.acquire() is False

    limiter.reset()
    assert limiter.acquire() is True
