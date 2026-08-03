"""
Base class and ``@tool`` decorator for Windows Developer MCP providers.

Every provider in the ``providers/`` package inherits from :class:`BaseProvider`.
Public methods that should be exposed as MCP tools are decorated with
:func:`tool`.

The :class:`ProviderRegistry` (``core/registry.py``) discovers these methods
automatically, so adding a new tool to a provider requires only:

1. Define the method with proper type hints and a docstring.
2. Decorate it with ``@tool``.
3. Register the provider once in ``server.py``.

No other files need to change.

Usage::

    from providers.base import BaseProvider, tool

    class MyProvider(BaseProvider):
        name = "my_provider"
        description = "Does something useful."

        @tool
        def do_thing(self, query: str) -> dict:
            \"\"\"Do something with query.\"\"\"
            result = self._run("my-tool " + query)
            return self._shell_response(result)
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any, TypeVar

from core.config import get_config
from core.context import RequestContext
from core.executor import get_executor
from utils.json_utils import error as make_error
from utils.json_utils import shell_result as make_shell_result
from utils.shell import Shell, ShellResult

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Attribute name used to mark tool methods.
_TOOL_MARKER: str = "_is_mcp_tool"


# ==============================================================================
# @tool Decorator
# ==============================================================================


def tool(fn: F) -> F:
    """
    Mark a provider method as an MCP tool.

    Methods decorated with ``@tool`` are discovered by :class:`ProviderRegistry`
    and automatically registered as MCP tools with their docstring as the
    tool description and their type-annotated signature as the parameter schema.

    The decorator is transparent — it returns the function unmodified except
    for setting a marker attribute, so tests can call decorated methods normally.

    Args:
        fn: The provider method to mark.

    Returns:
        The same function with ``_is_mcp_tool = True`` set.

    Example::

        @tool
        def git_status(self) -> dict:
            \"\"\"Return the current Git working tree status.\"\"\"
            ...
    """
    setattr(fn, _TOOL_MARKER, True)
    return fn


def is_tool(fn: Callable[..., Any]) -> bool:
    """Return ``True`` if ``fn`` has been decorated with ``@tool``."""
    return bool(getattr(fn, _TOOL_MARKER, False))


# ==============================================================================
# Base Provider
# ==============================================================================


class BaseProvider(ABC):
    """
    Abstract base class for all Windows Developer MCP providers.

    Subclasses must set the :attr:`name` and :attr:`description` class
    attributes and decorate their public tool methods with :func:`tool`.

    Providers are instantiated once and registered with the
    :class:`ProviderRegistry`. They are stateless — all mutable state lives
    in the session, executor, or config singletons.

    Attributes:
        name:        Unique snake_case identifier (e.g. ``"git"``).
        description: Short human-readable description shown in the registry.
    """

    name: str
    description: str

    @property
    def enabled(self) -> bool:
        """
        Return ``True`` if this provider is enabled in the application config.

        Reads ``providers.<name>`` from :func:`core.config.get_config`.
        Returns ``True`` for unknown provider names to avoid silently disabling
        providers that haven't been added to the config schema yet.
        """
        return get_config().providers.is_enabled(self.name)

    def get_tools(self) -> list[Callable[..., Any]]:
        """
        Return all bound methods decorated with :func:`@tool`.

        Called by :class:`ProviderRegistry` during MCP registration.

        Returns:
            A list of bound methods (not unbound functions) so that
            ``self`` is correctly captured when FastMCP calls them.
        """
        tools: list[Callable[..., Any]] = []
        for attr_name in dir(self.__class__):
            if attr_name.startswith("_"):
                continue
            unbound = getattr(self.__class__, attr_name, None)
            if unbound is not None and callable(unbound) and is_tool(unbound):
                tools.append(getattr(self, attr_name))
        return tools

    # ------------------------------------------------------------------
    # Protected Helpers for Subclasses
    # ------------------------------------------------------------------

    def _run(
        self,
        command: str,
        *,
        shell: Shell = Shell.POWERSHELL,
        cwd: Path | None = None,
        timeout: int | None = None,
        extra_env: dict[str, str] | None = None,
        tool_name: str = "",
    ) -> ShellResult:
        """
        Execute a shell command through the full security pipeline.

        This is the primary execution helper for provider methods. It creates
        a :class:`RequestContext` automatically from the ``tool_name`` parameter
        and delegates to :func:`core.executor.get_executor`.

        Args:
            command:   The command to run.
            shell:     Shell backend (default: PowerShell).
            cwd:       Working directory override.
            timeout:   Timeout override in seconds.
            extra_env: Additional environment variables.
            tool_name: The MCP tool name for audit logging (e.g. ``"git_status"``).

        Returns:
            A :class:`ShellResult` with stdout, stderr, exit code, and timing.
        """
        ctx = RequestContext(tool_name=tool_name or self.name)
        return get_executor().run(
            command,
            context=ctx,
            shell=shell,
            cwd=cwd,
            timeout=timeout,
            extra_env=extra_env,
        )

    def _run_safe(
        self,
        command: str,
        *,
        shell: Shell = Shell.POWERSHELL,
        cwd: Path | None = None,
        timeout: int | None = None,
        extra_env: dict[str, str] | None = None,
        tool_name: str = "",
    ) -> ShellResult:
        """
        Execute a command without raising on security failure.

        Like :meth:`_run`, but catches :class:`ValidationError` and
        :class:`PermissionDeniedError` and returns them as failed
        :class:`ShellResult` objects.

        Args:
            command:   The command to run.
            shell:     Shell backend.
            cwd:       Working directory override.
            timeout:   Timeout override.
            extra_env: Additional environment variables.
            tool_name: MCP tool name for logging.

        Returns:
            A :class:`ShellResult`. On security failure, exit_code is -1.
        """
        ctx = RequestContext(tool_name=tool_name or self.name)
        return get_executor().run_safe(
            command,
            context=ctx,
            shell=shell,
            cwd=cwd,
            timeout=timeout,
            extra_env=extra_env,
        )

    @staticmethod
    def _shell_response(result: ShellResult, tool_name: str = "") -> dict[str, Any]:
        """
        Convert a :class:`ShellResult` into a standardised tool response dict.

        Args:
            result:    The shell execution result.
            tool_name: The MCP tool name for the response envelope.

        Returns:
            A standardised :func:`utils.json_utils.shell_result` dict.
        """
        return make_shell_result(
            result.stdout,
            result.stderr,
            result.exit_code,
            tool=tool_name,
            duration_ms=result.duration_ms,
            command=result.command,
        )

    @staticmethod
    def _error_response(
        message: str,
        *,
        tool_name: str = "",
        code: str = "PROVIDER_ERROR",
        details: Any = None,
    ) -> dict[str, Any]:
        """
        Build a standardised error response dict.

        Args:
            message:   Human-readable error description.
            tool_name: The MCP tool name.
            code:      Machine-readable error code.
            details:   Optional additional context.

        Returns:
            A standardised :func:`utils.json_utils.error` dict.
        """
        return make_error(message, tool=tool_name, code=code, details=details)

    def __repr__(self) -> str:
        enabled = "enabled" if self.enabled else "disabled"
        return f"<{self.__class__.__name__} name={self.name!r} [{enabled}]>"
