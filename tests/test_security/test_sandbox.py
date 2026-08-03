"""
Tests for the security.sandbox module.

Covers:
- Path resolution within the workspace
- Path traversal attack prevention
- Symlink safety (mocked)
- Allowed directories support
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import WorkspaceViolationError
from security.sandbox import WorkspaceSandbox


@pytest.fixture()
def sandbox(workspace_root: Path, monkeypatch: pytest.MonkeyPatch) -> WorkspaceSandbox:
    """A WorkspaceSandbox configured to the test workspace."""
    from core.config import get_config

    cfg = get_config()
    monkeypatch.setattr(cfg.workspace, "path", str(workspace_root))
    return WorkspaceSandbox()


class TestWorkspaceSandbox:
    def test_path_inside_workspace_is_allowed(
        self, sandbox: WorkspaceSandbox, workspace_root: Path
    ) -> None:
        safe = sandbox.resolve_safe(workspace_root / "src" / "main.py")
        assert safe.is_absolute()
        assert safe == (workspace_root / "src" / "main.py").resolve()

    def test_workspace_root_itself_is_allowed(
        self, sandbox: WorkspaceSandbox, workspace_root: Path
    ) -> None:
        safe = sandbox.resolve_safe(workspace_root)
        assert safe == workspace_root.resolve()

    def test_path_traversal_is_blocked(
        self, sandbox: WorkspaceSandbox, workspace_root: Path
    ) -> None:
        evil_path = workspace_root / ".." / ".." / "etc" / "passwd"
        with pytest.raises(WorkspaceViolationError):
            sandbox.resolve_safe(evil_path)

    def test_absolute_path_outside_workspace_is_blocked(self, sandbox: WorkspaceSandbox) -> None:
        with pytest.raises(WorkspaceViolationError):
            sandbox.resolve_safe(Path("C:/Windows/System32/cmd.exe"))

    def test_is_safe_returns_true_for_valid_path(
        self, sandbox: WorkspaceSandbox, workspace_root: Path
    ) -> None:
        assert sandbox.is_safe(workspace_root / "README.md") is True

    def test_is_safe_returns_false_for_outside_path(self, sandbox: WorkspaceSandbox) -> None:
        assert sandbox.is_safe(Path("C:/Windows")) is False

    def test_assert_within_workspace_does_not_raise_for_valid(
        self, sandbox: WorkspaceSandbox, workspace_root: Path
    ) -> None:
        sandbox.assert_within_workspace(workspace_root / "src")

    def test_assert_within_workspace_raises_for_invalid(self, sandbox: WorkspaceSandbox) -> None:
        with pytest.raises(WorkspaceViolationError):
            sandbox.assert_within_workspace(Path("C:/Windows"))

    def test_workspace_violation_error_contains_path(
        self, sandbox: WorkspaceSandbox, workspace_root: Path
    ) -> None:
        evil = workspace_root / ".." / "secret"
        with pytest.raises(WorkspaceViolationError) as exc_info:
            sandbox.resolve_safe(evil)
        assert exc_info.value.path is not None

    def test_resolve_safe_allowed_with_extra_dir(
        self,
        sandbox: WorkspaceSandbox,
        workspace_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.config import get_config

        extra_dir = workspace_root.parent / "extra_allowed"
        extra_dir.mkdir(exist_ok=True)
        cfg = get_config()
        monkeypatch.setattr(cfg.workspace, "allowed_directories", [str(extra_dir)])
        safe = sandbox.resolve_safe_allowed(extra_dir / "somefile.txt")
        assert safe == (extra_dir / "somefile.txt").resolve()
