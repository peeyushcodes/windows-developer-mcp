"""
Node.js provider for Windows Developer MCP.

Provides Node.js runtime, npm, and package management tools.

Tools:
    node_version      — Node.js version
    npm_version       — npm version
    npm_list          — List installed packages
    npm_install       — Install packages
    npm_run           — Run an npm script
    npx_run           — Execute an npx command
    npm_info          — Package info from registry
    node_run_script   — Execute a .js file
"""

from __future__ import annotations

import logging
from typing import Any

from providers.base import BaseProvider, tool
from utils.json_utils import error as make_error

logger = logging.getLogger(__name__)


class NodeProvider(BaseProvider):
    """
    Provides Node.js runtime and npm package management tools.
    """

    name = "node"
    description = "Node.js version, npm, package management, and script execution."

    @tool
    def node_version(self) -> dict[str, Any]:
        """
        Return the installed Node.js version.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            node_version()
        """
        result = self._run_safe("node --version", tool_name="node_version")
        return self._shell_response(result, tool_name="node_version")

    @tool
    def npm_version(self) -> dict[str, Any]:
        """
        Return the installed npm version.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            npm_version()
        """
        result = self._run_safe("npm --version", tool_name="npm_version")
        return self._shell_response(result, tool_name="npm_version")

    @tool
    def npm_list(self, global_packages: bool = False, depth: int = 0) -> dict[str, Any]:
        """
        List installed npm packages.

        Args:
            global_packages: If True, list globally installed packages.
            depth:           Dependency depth to show (0 = top-level only).

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            npm_list()
            npm_list(global_packages=True)
            npm_list(depth=1)
        """
        global_flag = "--global" if global_packages else ""
        command = f"npm list {global_flag} --depth={depth}".strip()
        result = self._run_safe(command, tool_name="npm_list")
        return self._shell_response(result, tool_name="npm_list")

    @tool
    def npm_install(
        self,
        packages: str = "",
        save_dev: bool = False,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Install npm packages.

        Args:
            packages:  Space-separated package names. Leave empty to install
                       from package.json.
            save_dev:  If True, install as devDependencies (--save-dev).
            confirm:   Set to True to confirm when required by config.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            npm_install(confirm=True)
            npm_install("express lodash", confirm=True)
            npm_install("jest", save_dev=True, confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager
        from utils.json_utils import confirmation_required

        pm = PermissionManager()
        action = f"npm install {packages}".strip()
        if pm.requires_confirmation("npm_install"):
            try:
                pm.assert_confirmed(action=action, confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(action, tool="npm_install")

        dev_flag = "--save-dev" if save_dev else ""
        command = f"npm install {dev_flag} {packages}".strip()
        result = self._run_safe(command, tool_name="npm_install", timeout=120)
        return self._shell_response(result, tool_name="npm_install")

    @tool
    def npm_run(self, script: str, args: str = "") -> dict[str, Any]:
        """
        Run an npm script defined in package.json.

        Args:
            script: The script name (e.g. "build", "test", "start").
            args:   Optional arguments to pass after "--".

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            npm_run("build")
            npm_run("test")
            npm_run("start", args="--port 3000")
        """
        args_part = f"-- {args}" if args else ""
        command = f"npm run {script} {args_part}".strip()
        result = self._run_safe(command, tool_name="npm_run", timeout=300)
        return self._shell_response(result, tool_name="npm_run")

    @tool
    def npx_run(self, command: str, args: str = "", timeout: int = 120) -> dict[str, Any]:
        """
        Execute a command with npx.

        Args:
            command: The npx command or package to run.
            args:    Optional arguments.
            timeout: Execution timeout in seconds. Default: 120.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            npx_run("create-react-app", args="my-app")
            npx_run("prettier", args="--write src/")
        """
        full_command = f"npx {command} {args}".strip()
        result = self._run_safe(
            full_command, tool_name="npx_run", timeout=max(1, min(timeout, 600))
        )
        return self._shell_response(result, tool_name="npx_run")

    @tool
    def npm_info(self, package: str) -> dict[str, Any]:
        """
        Fetch information about an npm package from the registry.

        Args:
            package: The package name to look up.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            npm_info("react")
            npm_info("fastapi")
        """
        result = self._run_safe(f"npm info {package}", tool_name="npm_info")
        return self._shell_response(result, tool_name="npm_info")

    @tool
    def node_run_script(
        self,
        path: str,
        args: str = "",
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Execute a JavaScript file with Node.js.

        Args:
            path:    Path to the .js file (absolute or relative to cwd).
            args:    Optional arguments to pass to the script.
            timeout: Execution timeout in seconds. Default: 120.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            node_run_script("scripts/seed.js")
            node_run_script("app.js", args="--port 8080")
        """
        from pathlib import Path

        from core.exceptions import WorkspaceViolationError
        from core.session import get_session
        from security.sandbox import WorkspaceSandbox
        from utils.json_utils import not_found

        session = get_session()
        sandbox = WorkspaceSandbox()

        try:
            script_path = sandbox.resolve_safe(
                Path(path) if Path(path).is_absolute() else session.cwd / path
            )
        except WorkspaceViolationError as exc:
            return make_error(str(exc), tool="node_run_script", code="WORKSPACE_VIOLATION")

        if not script_path.exists():
            return not_found(f"Script {script_path}", tool="node_run_script")

        command = f'node "{script_path}" {args}'.strip()
        result = self._run_safe(
            command, tool_name="node_run_script", timeout=max(1, min(timeout, 3600))
        )
        return self._shell_response(result, tool_name="node_run_script")
