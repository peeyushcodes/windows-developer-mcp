"""
Miscellaneous helper utilities for Windows Developer MCP.

A collection of small, pure helper functions used across multiple modules.
Each function has a single clear responsibility with no side effects.

Usage::

    from utils.helpers import format_size, truncate, elapsed_ms

    print(format_size(1_048_576))   # "1.00 MB"
    print(truncate("Hello world", 5))  # "Hello…"
"""

from __future__ import annotations

import time
from typing import Any

# ==============================================================================
# String Helpers
# ==============================================================================


def truncate(text: str, max_len: int, *, suffix: str = "…") -> str:
    """
    Truncate ``text`` to at most ``max_len`` characters.

    Args:
        text:    The string to truncate.
        max_len: Maximum number of characters.
        suffix:  String appended when truncation occurs (default: ``"…"``).

    Returns:
        The original string if short enough, otherwise a truncated version
        ending with ``suffix``.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def indent(text: str, level: int = 1, *, width: int = 2) -> str:
    """
    Indent every line of ``text`` by ``level`` levels of ``width`` spaces.

    Args:
        text:  Multi-line string to indent.
        level: Number of indentation levels.
        width: Spaces per level.

    Returns:
        The indented string.
    """
    pad = " " * (level * width)
    return "\n".join(pad + line for line in text.splitlines())


def camel_to_snake(name: str) -> str:
    """
    Convert a CamelCase identifier to snake_case.

    Args:
        name: A CamelCase string (e.g. ``"GitProvider"``).

    Returns:
        The snake_case equivalent (e.g. ``"git_provider"``).
    """
    import re
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# ==============================================================================
# Size / Duration Formatting
# ==============================================================================


def format_size(num_bytes: int) -> str:
    """
    Format a byte count as a human-readable size string.

    Args:
        num_bytes: Size in bytes.

    Returns:
        A formatted string like ``"1.23 MB"``, ``"456.00 KB"``, etc.
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024 or unit == "TB":
            return f"{num_bytes:.2f} {unit}"
        num_bytes //= 1024
    return f"{num_bytes:.2f} TB"  # unreachable but satisfies type checkers


def format_duration(ms: int) -> str:
    """
    Format a millisecond duration as a human-readable string.

    Args:
        ms: Duration in milliseconds.

    Returns:
        A formatted string like ``"42ms"``, ``"1.2s"``, ``"3m 4s"``.
    """
    if ms < 1_000:
        return f"{ms}ms"
    seconds = ms / 1_000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


# ==============================================================================
# Dict Helpers
# ==============================================================================


def flatten_dict(d: dict[str, Any], *, sep: str = ".", prefix: str = "") -> dict[str, Any]:
    """
    Flatten a nested dictionary into a single-level dict with joined keys.

    Args:
        d:      The dictionary to flatten.
        sep:    Key separator (default: ``"."``).
        prefix: Key prefix for recursive calls.

    Returns:
        A flat dict where nested keys are joined by ``sep``.

    Example::

        flatten_dict({"a": {"b": 1, "c": 2}})
        # → {"a.b": 1, "a.c": 2}
    """
    result: dict[str, Any] = {}
    for key, value in d.items():
        full_key = f"{prefix}{sep}{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_dict(value, sep=sep, prefix=full_key))
        else:
            result[full_key] = value
    return result


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merge ``override`` into ``base``, returning a new dict.

    Values in ``override`` take precedence. Nested dicts are merged
    recursively rather than replaced.

    Args:
        base:     The base dictionary.
        override: Values to merge on top.

    Returns:
        A new merged dictionary (``base`` and ``override`` are not mutated).
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def filter_none(d: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of ``d`` with all ``None`` values removed.

    Args:
        d: The dictionary to filter.

    Returns:
        A new dict with no ``None`` values (shallow, top-level only).
    """
    return {k: v for k, v in d.items() if v is not None}


# ==============================================================================
# Time Helpers
# ==============================================================================


class Timer:
    """
    Context manager / utility class for measuring elapsed time.

    Usage::

        with Timer() as t:
            do_something()
        print(t.elapsed_ms)   # e.g. 142
    """

    def __init__(self) -> None:
        self._start: float = 0.0
        self._end: float = 0.0

    def __enter__(self) -> Timer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        self._end = time.monotonic()

    @property
    def elapsed_ms(self) -> int:
        """Elapsed milliseconds since the timer started."""
        end = self._end if self._end else time.monotonic()
        return int((end - self._start) * 1000)

    @property
    def elapsed_s(self) -> float:
        """Elapsed seconds since the timer started."""
        return self.elapsed_ms / 1000


def clamp(value: int, lo: int, hi: int) -> int:
    """
    Clamp ``value`` to the inclusive range ``[lo, hi]``.

    Args:
        value: The value to clamp.
        lo:    The minimum allowed value.
        hi:    The maximum allowed value.

    Returns:
        ``value`` if within range, otherwise ``lo`` or ``hi``.
    """
    return max(lo, min(hi, value))
