"""
Structured JSON result builders for Windows Developer MCP.

Every MCP tool returns a ``dict`` with a consistent schema so that AI
clients can reliably parse tool outputs regardless of which provider
generated them.

Schema overview::

    # Success
    {
        "status":      "success",
        "tool":        "git_status",
        "data":        { ... },         # or a string
        "duration_ms": 142
    }

    # Error
    {
        "status":  "error",
        "tool":    "git_status",
        "code":    "EXECUTION_ERROR",
        "message": "fatal: not a git repository"
    }

Usage::

    from utils.json_utils import success, error, tool_result

    return success({"branch": "main", "clean": True}, tool="git_status", duration_ms=80)
    return error("Not a git repository", tool="git_status", code="NOT_GIT_REPO")
"""

from __future__ import annotations

from typing import Any

# ==============================================================================
# Result Builders
# ==============================================================================


def success(
    data: Any,
    *,
    tool: str = "",
    duration_ms: int = 0,
) -> dict[str, Any]:
    """
    Build a successful tool result.

    Args:
        data:        The result payload. Can be any JSON-serialisable value
                     (dict, list, str, int, bool, None).
        tool:        The name of the MCP tool producing this result.
        duration_ms: Execution duration in milliseconds.

    Returns:
        A standardised success response dict.
    """
    return {
        "status": "success",
        "tool": tool,
        "data": data,
        "duration_ms": duration_ms,
    }


def error(
    message: str,
    *,
    tool: str = "",
    code: str = "ERROR",
    details: Any = None,
) -> dict[str, Any]:
    """
    Build an error tool result.

    Args:
        message: Human-readable error description.
        tool:    The name of the MCP tool that failed.
        code:    Machine-readable error code (e.g. ``"PERMISSION_DENIED"``).
        details: Optional additional context (exception info, partial output).

    Returns:
        A standardised error response dict.
    """
    result: dict[str, Any] = {
        "status": "error",
        "tool": tool,
        "code": code,
        "message": message,
    }
    if details is not None:
        result["details"] = details
    return result


def shell_result(
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    tool: str = "",
    duration_ms: int = 0,
    command: str = "",
) -> dict[str, Any]:
    """
    Build a result dict from raw shell output.

    This is the standard response shape for terminal and git commands
    that run shell processes directly.

    Args:
        stdout:      Process standard output.
        stderr:      Process standard error.
        exit_code:   Process return code.
        tool:        The MCP tool name.
        duration_ms: Execution duration in milliseconds.
        command:     The command that was executed (for context).

    Returns:
        A standardised shell result dict (status is ``"success"`` when
        exit_code is 0, otherwise ``"error"``).
    """
    succeeded = exit_code == 0
    return {
        "status": "success" if succeeded else "error",
        "tool": tool,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "output": stdout if stdout else stderr,
        "command": command,
        "duration_ms": duration_ms,
    }


def not_found(resource: str, *, tool: str = "") -> dict[str, Any]:
    """
    Build a standardised 'not found' error result.

    Args:
        resource: Description of what was not found (e.g. ``"file /foo/bar.py"``).
        tool:     The MCP tool name.

    Returns:
        An error result with code ``"NOT_FOUND"``.
    """
    return error(
        f"{resource} not found.",
        tool=tool,
        code="NOT_FOUND",
    )


def permission_denied(reason: str, *, tool: str = "") -> dict[str, Any]:
    """
    Build a standardised permission denied error result.

    Args:
        reason: Explanation of why permission was denied.
        tool:   The MCP tool name.

    Returns:
        An error result with code ``"PERMISSION_DENIED"``.
    """
    return error(reason, tool=tool, code="PERMISSION_DENIED")


def validation_failed(reason: str, *, tool: str = "") -> dict[str, Any]:
    """
    Build a standardised validation failure result.

    Args:
        reason: What failed validation and why.
        tool:   The MCP tool name.

    Returns:
        An error result with code ``"VALIDATION_ERROR"``.
    """
    return error(reason, tool=tool, code="VALIDATION_ERROR")


def confirmation_required(action: str, *, tool: str = "") -> dict[str, Any]:
    """
    Build a result indicating that explicit confirmation is required.

    Args:
        action: The destructive action that requires confirmation.
        tool:   The MCP tool name.

    Returns:
        An error result with code ``"CONFIRMATION_REQUIRED"`` and instructions
        for the AI to pass ``confirm=True`` on the next call.
    """
    return error(
        f"Action '{action}' requires explicit confirmation. "
        "Call this tool again with confirm=True to proceed.",
        tool=tool,
        code="CONFIRMATION_REQUIRED",
    )
