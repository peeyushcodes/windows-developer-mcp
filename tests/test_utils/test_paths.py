"""Unit tests for utils/paths.py."""

from pathlib import Path

import pytest

from utils.paths import (
    ensure_directory,
    find_upward,
    has_extension,
    is_within,
    normalize_path,
    posix_path,
    resolve_relative,
    safe_relative,
    windows_path,
)


class TestPaths:
    def test_normalize_path(self, tmp_path):
        p = normalize_path(tmp_path / "sub/..")
        assert p == tmp_path.resolve()

    def test_is_within(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        child = root / "child/file.txt"
        assert is_within(child, root=root) is True

        outside = tmp_path / "outside"
        assert is_within(outside, root=root) is False

    def test_resolve_relative(self, tmp_path):
        base = tmp_path / "base"
        base.mkdir()
        rel = resolve_relative("sub/file.txt", base=base)
        assert rel == (base / "sub/file.txt").resolve()

        abs_p = (tmp_path / "abs.txt").resolve()
        assert resolve_relative(abs_p, base=base) == abs_p

    def test_safe_relative(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        child = root / "file.txt"
        rel = safe_relative(child, root=root)
        assert rel == Path("file.txt")

        outside = tmp_path / "outside.txt"
        assert safe_relative(outside, root=root) == outside

    def test_ensure_directory(self, tmp_path):
        d = tmp_path / "a/b/c"
        created = ensure_directory(d)
        assert created.is_dir()

        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(NotADirectoryError):
            ensure_directory(f)

    def test_windows_and_posix_path(self):
        p = Path("foo/bar/baz")
        assert "/" in posix_path(p)
        assert r"foo\bar\baz" in windows_path(p) or "foo" in windows_path(p)

    def test_has_extension(self):
        p = Path("code.py")
        assert has_extension(p, ".py", ".toml") is True
        assert has_extension(p, ".js") is False

    def test_find_upward(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()
        target = root / "pyproject.toml"
        target.write_text("[project]")

        sub = root / "a/b/c"
        sub.mkdir(parents=True)

        found = find_upward(sub, "pyproject.toml")
        assert found == target

        not_found = find_upward(sub, "nonexistent.file")
        assert not_found is None
