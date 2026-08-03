"""
Permission management for Windows Developer MCP.

The :class:`PermissionManager` is the second gate in the execution pipeline,
consulted after the :class:`CommandValidator` approves a command.

Responsibilities:
- Enforce read-only mode (block all write/execute operations)
- Identify commands that require explicit user confirmation
- Check whether a given path is accessible from the current configuration

Usage::

    from security.permissions import PermissionManager

    pm = PermissionManager()
    pm.assert_not_read_only("delete_file")
    pm.assert_confirmed(action="delete_file", confirm=False)
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from core.config import get_config
from core.exceptions import ConfirmationRequiredError, ReadOnlyModeError

logger = logging.getLogger(__name__)


# ==============================================================================
# Write-Operation Patterns
# ==============================================================================

# Commands/operations classified as writes.
# Used to enforce read-only mode.
_WRITE_PATTERNS: tuple[str, ...] = (
    r"\bwrite\b",
    r"\bcopy\b",
    r"\bmove\b",
    r"\bdelete\b",
    r"\bcreate\b",
    r"\bmkdir\b",
    r"\bmkdir\b",
    r"\bremove\b",
    r"\binstall\b",
    r"\buninstall\b",
    r"\bcommit\b",
    r"\bpush\b",
    r"\bpull\b",
    r"\bclone\b",
    r"\bdocker\b",
    r"\bnpm\s+install\b",
    r"\bpip\s+install\b",
    r"\bpip\s+uninstall\b",
    r"\brun_powershell\b",
    r"\brun_cmd\b",
    r"\brun_script\b",
)

_COMPILED_WRITE: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in _WRITE_PATTERNS
)


# ==============================================================================
# Destructive Action Identifiers
# ==============================================================================

# Tool names and action verbs that always require explicit confirmation.
# Keys are matched case-insensitively against the tool name.
_CONFIRMATION_REQUIRED_TOOLS: frozenset[str] = frozenset(
    {
        "delete_file",
        "move_file",
        "write_file",
        "git_push",
        "git_commit",
        "pip_uninstall_package",
        "docker_remove_container",
        "docker_remove_image",
        "sqlite_execute",  # write queries only — provider handles the distinction
    }
)


# ==============================================================================
# Permission Manager
# ==============================================================================


@dataclass
class PermissionCheck:
    """
    Result of a permission check.

    Attributes:
        allowed:  ``True`` if the operation is permitted.
        reason:   Human-readable explanation if ``allowed`` is ``False``.
        code:     Machine-readable error code if ``allowed`` is ``False``.
    """

    allowed: bool
    reason: str = ""
    code: str = ""


class PermissionManager:
    """
    Enforces read-only mode and confirmation requirements.

    This class is stateless and thread-safe. Configuration is read from
    :func:`core.config.get_config` on every call.
    """

    def check_read_only(self, tool_name: str, command: str = "") -> PermissionCheck:
        """
        Check whether a write operation is permitted given the current config.

        Args:
            tool_name: The MCP tool name attempting the write.
            command:   Optional command string for pattern matching.

        Returns:
            A :class:`PermissionCheck` — ``allowed=True`` unless read-only
            mode is active and the operation looks like a write.
        """
        cfg = get_config()
        if not cfg.workspace.read_only:
            return PermissionCheck(allowed=True)

        # In read-only mode, check if this tool or command implies a write.
        target = (tool_name + " " + command).lower().replace("_", " ")
        for compiled in _COMPILED_WRITE:
            if compiled.search(target):
                return PermissionCheck(
                    allowed=False,
                    reason=(
                        f"Operation '{tool_name}' is not permitted in read-only mode. "
                        "Set workspace.read_only = false in config.toml to enable writes."
                    ),
                    code="READ_ONLY_MODE",
                )
        return PermissionCheck(allowed=True)

    def assert_not_read_only(self, tool_name: str, command: str = "") -> None:
        """
        Assert that the current operation is not blocked by read-only mode.

        Args:
            tool_name: The MCP tool name attempting the write.
            command:   Optional command string for pattern matching.

        Raises:
            ReadOnlyModeError: If read-only mode is active and this is a write.
        """
        result = self.check_read_only(tool_name, command)
        if not result.allowed:
            raise ReadOnlyModeError(result.reason)

    def requires_confirmation(self, tool_name: str) -> bool:
        """
        Return ``True`` if this tool requires explicit confirmation.

        Args:
            tool_name: The MCP tool name to check.

        Returns:
            ``True`` if the tool is in the confirmation-required set and
            ``security.require_confirmation`` is enabled in config.
        """
        cfg = get_config()
        if not cfg.security.require_confirmation:
            return False
        return tool_name.lower() in _CONFIRMATION_REQUIRED_TOOLS

    def assert_confirmed(self, *, action: str, confirm: bool) -> None:
        """
        Assert that a destructive action has been explicitly confirmed.

        Args:
            action:  A description of the action requiring confirmation.
            confirm: The value of the ``confirm`` parameter passed by the caller.

        Raises:
            ConfirmationRequiredError: If ``confirm`` is ``False``.
        """
        if not confirm:
            raise ConfirmationRequiredError(
                f"Action '{action}' requires explicit confirmation. "
                "Call this tool again with confirm=True to proceed."
            )
        logger.info("Destructive action confirmed by caller: %s", action)

    def is_confirmation_required_for_tool(self, tool_name: str) -> bool:
        """
        Public helper for providers to check before executing destructive ops.

        Args:
            tool_name: The MCP tool name.

        Returns:
            ``True`` if ``require_confirmation`` is enabled and this tool
            is in the destructive set.
        """
        return self.requires_confirmation(tool_name)
