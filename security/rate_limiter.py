"""
Rate limiting mechanism for Windows Developer MCP tool calls.

Implements a sliding-window rate limiter to protect the server from tool execution
flooding or automated runaway loops.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter for tracking tool invocation frequencies.

    Attributes:
        max_calls: Maximum allowed tool executions in the window.
        window_seconds: Duration of the sliding window in seconds.
    """

    def __init__(self, max_calls: int = 60, window_seconds: int = 60) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []

    def acquire(self) -> bool:
        """
        Attempt to acquire a rate-limiting token.

        Returns:
            True if invocation is permitted, False if rate limit is exceeded.
        """
        now = time.time()
        cutoff = now - self.window_seconds
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

        if len(self._timestamps) >= self.max_calls:
            logger.warning(
                "Rate limit exceeded: %d calls within %ds window.",
                len(self._timestamps),
                self.window_seconds,
            )
            return False

        self._timestamps.append(now)
        return True

    def reset(self) -> None:
        """Reset the rate limiter state."""
        self._timestamps.clear()

    def get_stats(self) -> dict[str, Any]:
        """Return current rate limiter usage stats."""
        now = time.time()
        cutoff = now - self.window_seconds
        active_calls = sum(1 for ts in self._timestamps if ts > cutoff)
        return {
            "max_calls": self.max_calls,
            "window_seconds": self.window_seconds,
            "active_calls_in_window": active_calls,
            "remaining_calls": max(0, self.max_calls - active_calls),
        }
