"""Unit tests for utils/helpers.py."""

import time

from utils.helpers import (
    Timer,
    camel_to_snake,
    clamp,
    deep_merge,
    filter_none,
    flatten_dict,
    format_duration,
    format_size,
    indent,
    truncate,
)


class TestHelpers:
    def test_truncate(self):
        assert truncate("hello world", 20) == "hello world"
        assert truncate("hello world", 5) == "hell…"
        assert truncate("hello world", 5, suffix="!") == "hell!"

    def test_indent(self):
        text = "line1\nline2"
        ind = indent(text, level=1, width=2)
        assert ind == "  line1\n  line2"

    def test_camel_to_snake(self):
        assert camel_to_snake("GitProvider") == "git_provider"
        assert camel_to_snake("HTTPClientTool") == "http_client_tool"

    def test_format_size(self):
        assert format_size(500) == "500.00 B"
        assert format_size(2048) == "2.00 KB"
        assert format_size(1048576) == "1.00 MB"

    def test_format_duration(self):
        assert format_duration(500) == "500ms"
        assert format_duration(1500) == "1.5s"
        assert format_duration(125000) == "2m 5s"

    def test_flatten_dict(self):
        d = {"a": {"b": 1, "c": {"d": 2}}, "e": 3}
        flat = flatten_dict(d)
        assert flat == {"a.b": 1, "a.c.d": 2, "e": 3}

    def test_deep_merge(self):
        base = {"a": 1, "b": {"x": 10}}
        override = {"b": {"y": 20}, "c": 3}
        merged = deep_merge(base, override)
        assert merged == {"a": 1, "b": {"x": 10, "y": 20}, "c": 3}

    def test_filter_none(self):
        d = {"a": 1, "b": None, "c": "hello"}
        filtered = filter_none(d)
        assert filtered == {"a": 1, "c": "hello"}

    def test_timer(self):
        with Timer() as t:
            time.sleep(0.01)
        assert t.elapsed_ms >= 0
        assert t.elapsed_s >= 0

    def test_clamp(self):
        assert clamp(5, 1, 10) == 5
        assert clamp(-5, 1, 10) == 1
        assert clamp(15, 1, 10) == 10
