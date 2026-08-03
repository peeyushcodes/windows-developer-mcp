"""
Workspace sandbox enforcement for Windows Developer MCP.

The :class:`WorkspaceSandbox` ensures that all file system operations
stay within the configured workspace boundary. It is a defence-in-depth
measure applied **after** the validator and permission manager.

Paths are resolved to absolute form before comparison, so symlinks,
``../`` traversal, and UNC paths cannot escape the workspace.

Usage::

    from security.sandbox import WorkspaceSandbox

    sandbox = WorkspaceSandbox()
    safe_path = sandbox.resolve_safe(user_input="/projects/../../../etc/passwd")
    # raises WorkspaceViolationError
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.config import get_config
from core.exceptions import WorkspaceViolationError
from utils.paths import is_within, normalize_path

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class WorkspaceSandbox:
    """
    Restricts file system access to the configured workspace directory.

    The workspace root is read from ``workspace.path`` in the application
    config. All paths are resolved to absolute form before the containment
    check, defeating all known path traversal techniques.

    This class is stateless. The workspace root is re-read from config on
    every call so that test overrides are reflected immediately.
    """

    @property
    def workspace_root(self) -> Path:
        """The resolved, absolute workspace root directory."""
        return normalize_path(get_config().workspace.path)

    def is_safe(self, path: str | Path) -> bool:
        """
        Return ``True`` if ``path`` is within the workspace boundary.

        Args:
            path: The path to check. May be relative or absolute.

        Returns:
            ``True`` if the resolved path is inside the workspace root.
        """
        resolved = normalize_path(path)
        return is_within(resolved, root=self.workspace_root)

    def resolve_safe(self, path: str | Path) -> Path:
        """
        Resolve and validate a path, raising if it escapes the workspace.

        Args:
            path: The path to resolve and validate.

        Returns:
            The resolved absolute ``Path`` if it is within the workspace.

        Raises:
            WorkspaceViolationError: If the resolved path is outside the workspace.
        """
        resolved = normalize_path(path)
        root = self.workspace_root

        if not is_within(resolved, root=root):
            logger.warning(
                "Workspace violation: %s is outside workspace root %s", resolved, root
            )
            raise WorkspaceViolationError(
                f"Path {resolved!r} is outside the workspace boundary ({root!r}). "
                "Update workspace.path or workspace.allowed_directories in config.toml "
                "to grant access.",
                path=str(resolved),
            )

        logger.debug("Path validated within workspace: %s", resolved)
        return resolved

    def resolve_safe_allowed(self, path: str | Path) -> Path:
        """
        Resolve and validate against the workspace and any extra allowed directories.

        If ``workspace.allowed_directories`` is non-empty in config, the path
        must be within the workspace root **or** one of those directories.

        Args:
            path: The path to resolve and validate.

        Returns:
            The resolved absolute ``Path`` if allowed.

        Raises:
            WorkspaceViolationError: If the path is not within any allowed location.
        """
        resolved = normalize_path(path)
        root = self.workspace_root

        if is_within(resolved, root=root):
            return resolved

        allowed_dirs = get_config().workspace.allowed_directories
        for allowed_str in allowed_dirs:
            allowed = normalize_path(allowed_str)
            if is_within(resolved, root=allowed):
                logger.debug(
                    "Path %s allowed via extra allowed_directory %s", resolved, allowed
                )
                return resolved

        raise WorkspaceViolationError(
            f"Path {resolved!r} is outside the workspace ({root!r}) "
            f"and not in any of the allowed directories ({allowed_dirs!r}).",
            path=str(resolved),
        )

    def assert_within_workspace(self, path: str | Path) -> None:
        """
        Assert that ``path`` is within the workspace; raise on violation.

        Convenience wrapper around :meth:`resolve_safe` that discards
        the returned value.

        Args:
            path: The path to validate.

        Raises:
            WorkspaceViolationError: If the path escapes the workspace.
        """
        self.resolve_safe(path)
