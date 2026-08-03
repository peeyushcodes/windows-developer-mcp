"""
Terminal provider for Windows Developer MCP.

Exposes PowerShell and CMD execution, working directory management,
script execution, and environment variable inspection as MCP tools.

All commands pass through the full security pipeline:
validator → permission manager → audit logger → executor → result.

Tools:
    run_powershell           — Execute a PowerShell command
    run_cmd                  — Execute a CMD command
    run_script               — Execute a .ps1 or .bat script file
    get_working_directory    — Return the current working directory
    set_working_directory    — Change the current working directory
    get_environment_variable — Read a single environment variable
    list_environment_variables — List all environment variables
    get_session_info         — Return session metadata snapshot
    get_session_history      — Return recent command history
    clear_session_history    — Clear the command history
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from core.session import get_session
from providers.base import BaseProvider, tool
from utils.shell import Shell

logger = logging.getLogger(__name__)


class TerminalProvider(BaseProvider):
    """
    Provides direct shell execution via PowerShell and CMD.

    This is the most privileged provider — it allows arbitrary command
    execution — so it relies heavily on the security pipeline (validator,
    permission manager, sandbox) for safety.

    All outputs are capped at ``security.max_output_length`` characters
    (configured in ``config.toml``) to protect the AI context window.
    """

    name = "terminal"
    description = "PowerShell and CMD execution, working directory, environment variables."

    # ------------------------------------------------------------------
    # Command Execution
    # ------------------------------------------------------------------

    @tool
    def run_powershell(self, command: str, timeout: int = 60) -> dict[str, Any]:
        """
        Execute a PowerShell command and return the output.

        The command passes through the full security validation pipeline
        before execution. Dangerous commands (format, shutdown, etc.) are
        blocked automatically.

        Args:
            command: The PowerShell command or expression to execute.
            timeout: Maximum execution time in seconds (1–3600). Default: 60.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output,
            command, duration_ms.

        Examples:
            run_powershell("Get-Date")
            run_powershell("Get-ChildItem C:\\projects")
            run_powershell("Write-Host 'Hello, World!'")
        """
        timeout = max(1, min(timeout, 3600))
        result = self._run_safe(
            command,
            shell=Shell.POWERSHELL,
            timeout=timeout,
            tool_name="run_powershell",
        )
        return self._shell_response(result, tool_name="run_powershell")

    @tool
    def run_cmd(self, command: str, timeout: int = 60) -> dict[str, Any]:
        """
        Execute a CMD command and return the output.

        Useful for legacy batch operations, tools that behave differently
        under CMD, or when PowerShell is unavailable.

        Args:
            command: The CMD command to execute.
            timeout: Maximum execution time in seconds (1–3600). Default: 60.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output,
            command, duration_ms.

        Examples:
            run_cmd("dir")
            run_cmd("echo %PATH%")
            run_cmd("ipconfig /all")
        """
        timeout = max(1, min(timeout, 3600))
        result = self._run_safe(
            command,
            shell=Shell.CMD,
            timeout=timeout,
            tool_name="run_cmd",
        )
        return self._shell_response(result, tool_name="run_cmd")

    @tool
    def run_script(self, path: str, args: str = "", timeout: int = 120) -> dict[str, Any]:
        """
        Execute a PowerShell (.ps1) or batch (.bat/.cmd) script file.

        Resolves the script path relative to the current working directory.
        The script must exist within the configured workspace boundary.

        Args:
            path:    Path to the script file (.ps1, .bat, or .cmd).
            args:    Optional arguments to pass to the script.
            timeout: Maximum execution time in seconds. Default: 120.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output,
            command, duration_ms.

        Examples:
            run_script("scripts/setup.ps1")
            run_script("build.bat", args="/release")
        """
        from core.exceptions import WorkspaceViolationError
        from security.sandbox import WorkspaceSandbox
        from utils.json_utils import error as make_error

        sandbox = WorkspaceSandbox()
        session = get_session()

        try:
            script_path = sandbox.resolve_safe(
                Path(path) if Path(path).is_absolute() else session.cwd / path
            )
        except WorkspaceViolationError as exc:
            return make_error(str(exc), tool="run_script", code="WORKSPACE_VIOLATION")

        if not script_path.exists():
            from utils.json_utils import not_found

            return not_found(f"Script {script_path}", tool="run_script")

        suffix = script_path.suffix.lower()
        if suffix in (".ps1",):
            command = f"& '{script_path}' {args}".strip()
            shell = Shell.POWERSHELL
        elif suffix in (".bat", ".cmd"):
            command = f'"{script_path}" {args}'.strip()
            shell = Shell.CMD
        else:
            return self._error_response(
                f"Unsupported script type: {suffix!r}. Use .ps1, .bat, or .cmd.",
                tool_name="run_script",
                code="UNSUPPORTED_SCRIPT_TYPE",
            )

        result = self._run_safe(
            command,
            shell=shell,
            timeout=max(1, min(timeout, 3600)),
            tool_name="run_script",
        )
        return self._shell_response(result, tool_name="run_script")

    # ------------------------------------------------------------------
    # Working Directory
    # ------------------------------------------------------------------

    @tool
    def get_working_directory(self) -> dict[str, Any]:
        """
        Return the current session working directory.

        The working directory persists across all tool calls within the
        same server session. It defaults to the user's home directory on
        startup.

        Returns:
            A dict with keys: status, data (containing cwd, exists, is_dir).

        Examples:
            get_working_directory()
        """
        from utils.json_utils import success

        cwd = get_session().cwd
        return success(
            {
                "cwd": str(cwd),
                "exists": cwd.exists(),
                "is_dir": cwd.is_dir(),
            },
            tool="get_working_directory",
        )

    @tool
    def set_working_directory(self, path: str) -> dict[str, Any]:
        """
        Change the current session working directory.

        The new directory must exist and must be within the configured
        workspace boundary. Relative paths are resolved against the
        current working directory.

        Args:
            path: The target directory (absolute or relative).

        Returns:
            A dict with keys: status, data (containing old_cwd, new_cwd).

        Examples:
            set_working_directory("C:/projects/myapp")
            set_working_directory("..")
            set_working_directory("src")
        """
        from core.exceptions import WorkspaceViolationError
        from security.sandbox import WorkspaceSandbox
        from utils.json_utils import error as make_error
        from utils.json_utils import success

        session = get_session()
        old_cwd = str(session.cwd)
        sandbox = WorkspaceSandbox()

        try:
            # Validate the target is in the workspace
            target = Path(path) if Path(path).is_absolute() else session.cwd / path
            sandbox.assert_within_workspace(target)

            # Change directory (session validates existence)
            new_cwd = session.change_directory(path)
            return success(
                {"old_cwd": old_cwd, "new_cwd": str(new_cwd)},
                tool="set_working_directory",
            )
        except WorkspaceViolationError as exc:
            return make_error(str(exc), tool="set_working_directory", code="WORKSPACE_VIOLATION")
        except FileNotFoundError as exc:
            return make_error(str(exc), tool="set_working_directory", code="NOT_FOUND")
        except NotADirectoryError as exc:
            return make_error(str(exc), tool="set_working_directory", code="NOT_A_DIRECTORY")

    # ------------------------------------------------------------------
    # Environment Variables
    # ------------------------------------------------------------------

    @tool
    def get_environment_variable(self, name: str) -> dict[str, Any]:
        """
        Return the value of an environment variable.

        Checks session-scoped overrides first, then falls back to the
        inherited process environment.

        Args:
            name: The environment variable name (case-insensitive on Windows).

        Returns:
            A dict with keys: status, data (containing name, value, source).
            source is "session" if set via the session, otherwise "process".

        Examples:
            get_environment_variable("PATH")
            get_environment_variable("VIRTUAL_ENV")
            get_environment_variable("JAVA_HOME")
        """
        from utils.json_utils import not_found, success

        session = get_session()

        # Session overrides take priority
        session_value = session.get_env(name)
        if session_value is not None:
            return success(
                {"name": name, "value": session_value, "source": "session"},
                tool="get_environment_variable",
            )

        # Fall back to process environment (case-insensitive on Windows)
        value = os.environ.get(name) or os.environ.get(name.upper())
        if value is not None:
            return success(
                {"name": name, "value": value, "source": "process"},
                tool="get_environment_variable",
            )

        return not_found(f"Environment variable {name!r}", tool="get_environment_variable")

    @tool
    def list_environment_variables(
        self,
        filter_prefix: str = "",
    ) -> dict[str, Any]:
        """
        List all environment variables visible to the MCP server process.

        Returns both process-level and session-scoped overrides. Session
        overrides are marked with ``source: "session"`` in the output.

        Args:
            filter_prefix: Optional prefix to filter variable names
                           (case-insensitive). Leave empty to list all.

        Returns:
            A dict with keys: status, data (list of {name, value, source}).

        Examples:
            list_environment_variables()
            list_environment_variables("PATH")
            list_environment_variables("PYTHON")
        """
        from utils.json_utils import success

        session = get_session()
        session_env = session.get_all_env()
        prefix_lower = filter_prefix.lower()

        variables = []

        # Process environment
        for key, value in sorted(os.environ.items()):
            if prefix_lower and not key.lower().startswith(prefix_lower):
                continue
            # Session override takes precedence — don't double-list
            if key in session_env:
                continue
            variables.append({"name": key, "value": value, "source": "process"})

        # Session overrides
        for key, value in sorted(session_env.items()):
            if prefix_lower and not key.lower().startswith(prefix_lower):
                continue
            variables.append({"name": key, "value": value, "source": "session"})

        variables.sort(key=lambda v: v["name"])

        return success(
            {"count": len(variables), "variables": variables},
            tool="list_environment_variables",
        )

    # ------------------------------------------------------------------
    # Session Introspection
    # ------------------------------------------------------------------

    @tool
    def get_session_info(self) -> dict[str, Any]:
        """
        Return a snapshot of the current session state.

        Includes the working directory, last exit code, active virtual
        environment, active Git repository, active project, and session
        start time.

        Returns:
            A dict with keys: status, data (session snapshot).

        Examples:
            get_session_info()
        """
        from utils.json_utils import success

        return success(get_session().to_dict(), tool="get_session_info")

    @tool
    def get_session_history(self, limit: int = 20) -> dict[str, Any]:
        """
        Return recent command history for the current session.

        History entries include the command, tool name, exit code, timestamp,
        and duration. History is capped at 500 entries.

        Args:
            limit: Maximum number of entries to return (1–500). Default: 20.

        Returns:
            A dict with keys: status, data (list of history entries).

        Examples:
            get_session_history()
            get_session_history(limit=50)
        """
        from utils.json_utils import success

        limit = max(1, min(limit, 500))
        history = get_session().get_history(limit=limit)
        return success(
            {"count": len(history), "entries": history},
            tool="get_session_history",
        )

    @tool
    def clear_session_history(self) -> dict[str, Any]:
        """
        Clear the session command history.

        This does not affect the working directory, environment variables,
        or any other session state. Only the command history is cleared.

        Returns:
            A dict with keys: status, data (confirmation message).

        Examples:
            clear_session_history()
        """
        from utils.json_utils import success

        get_session().clear_history()
        return success({"message": "Session history cleared."}, tool="clear_session_history")
