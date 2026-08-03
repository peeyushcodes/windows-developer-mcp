"""
Python provider for Windows Developer MCP.

Exposes Python environment management, package operations, virtual
environment management, and script execution as MCP tools.

Tools:
    python_version       — Python interpreter version
    pip_version          — pip version
    list_packages        — Installed packages
    install_package      — Install a package with pip
    uninstall_package    — Uninstall a package with pip
    pip_freeze           — Export requirements.txt format
    check_package        — Check if a package is installed
    create_venv          — Create a virtual environment
    run_python_script    — Execute a Python script
    python_info          — Full Python environment info
"""

from __future__ import annotations

import logging
from typing import Any

from providers.base import BaseProvider, tool

logger = logging.getLogger(__name__)


class PythonProvider(BaseProvider):
    """
    Provides Python environment management and package operations.

    Commands are executed using the Python interpreter on PATH, or the
    active virtual environment's interpreter if one is set in the session.
    """

    name = "python"
    description = "Python version, pip, virtual environments, packages, and script execution."

    def _python_cmd(self) -> str:
        """Return the Python executable to use (venv-aware)."""
        from core.session import get_session

        session = get_session()
        venv = session.active_venv
        if venv is not None:
            py = venv / "Scripts" / "python.exe"
            if py.exists():
                return str(py)
        return "python"

    def _pip_cmd(self) -> str:
        """Return the pip executable to use (venv-aware)."""
        from core.session import get_session

        session = get_session()
        venv = session.active_venv
        if venv is not None:
            pip = venv / "Scripts" / "pip.exe"
            if pip.exists():
                return str(pip)
        return "pip"

    # ------------------------------------------------------------------
    # Version / Info
    # ------------------------------------------------------------------

    @tool
    def python_version(self) -> dict[str, Any]:
        """
        Return the current Python interpreter version.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            python_version()
        """
        result = self._run_safe(f"{self._python_cmd()} --version", tool_name="python_version")
        return self._shell_response(result, tool_name="python_version")

    @tool
    def pip_version(self) -> dict[str, Any]:
        """
        Return the current pip version.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            pip_version()
        """
        result = self._run_safe(f"{self._pip_cmd()} --version", tool_name="pip_version")
        return self._shell_response(result, tool_name="pip_version")

    @tool
    def python_info(self) -> dict[str, Any]:
        """
        Return comprehensive Python environment information.

        Includes version, executable path, platform, prefix, and
        active virtual environment (if any).

        Returns:
            A dict with keys: status, data (detailed env info).

        Examples:
            python_info()
        """
        from core.session import get_session
        from utils.json_utils import error as make_error
        from utils.json_utils import success

        py = self._python_cmd()
        script = (
            "import sys, platform; "
            "print(sys.version); "
            "print(sys.executable); "
            "print(platform.platform()); "
            "print(sys.prefix); "
            "print(sys.base_prefix)"
        )
        result = self._run_safe(f'{py} -c "{script}"', tool_name="python_info")
        if not result.succeeded:
            return make_error(result.stderr, tool="python_info", code="EXECUTION_ERROR")

        lines = result.stdout.splitlines()
        session = get_session()
        return success(
            {
                "version": lines[0] if len(lines) > 0 else "",
                "executable": lines[1] if len(lines) > 1 else py,
                "platform": lines[2] if len(lines) > 2 else "",
                "prefix": lines[3] if len(lines) > 3 else "",
                "base_prefix": lines[4] if len(lines) > 4 else "",
                "in_virtualenv": (lines[3] != lines[4] if len(lines) > 4 else False),
                "active_venv": str(session.active_venv) if session.active_venv else None,
            },
            tool="python_info",
        )

    # ------------------------------------------------------------------
    # Package Management
    # ------------------------------------------------------------------

    @tool
    def list_packages(self, format: str = "table") -> dict[str, Any]:
        """
        List all installed Python packages.

        Args:
            format: Output format — "table" (default) or "json".

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            list_packages()
            list_packages(format="json")
        """
        pip = self._pip_cmd()
        command = f"{pip} list --format=json" if format == "json" else f"{pip} list"
        result = self._run_safe(command, tool_name="list_packages")
        return self._shell_response(result, tool_name="list_packages")

    @tool
    def pip_freeze(self) -> dict[str, Any]:
        """
        Output installed packages in requirements.txt format.

        Useful for generating a requirements.txt file or auditing
        the exact package versions in the current environment.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            pip_freeze()
        """
        result = self._run_safe(f"{self._pip_cmd()} freeze", tool_name="pip_freeze")
        return self._shell_response(result, tool_name="pip_freeze")

    @tool
    def check_package(self, package: str) -> dict[str, Any]:
        """
        Check whether a package is installed and return its version.

        Args:
            package: The package name to check (e.g. "fastmcp", "requests").

        Returns:
            A dict with keys: status, data (containing installed bool, version).

        Examples:
            check_package("fastmcp")
            check_package("numpy")
        """
        from utils.json_utils import success

        result = self._run_safe(f"{self._pip_cmd()} show {package}", tool_name="check_package")
        if result.succeeded and result.stdout:
            # Parse version from pip show output
            version = ""
            for line in result.stdout.splitlines():
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    break
            return success(
                {"package": package, "installed": True, "version": version},
                tool="check_package",
            )
        return success(
            {"package": package, "installed": False, "version": None},
            tool="check_package",
        )

    @tool
    def install_package(
        self,
        package: str,
        version: str = "",
        upgrade: bool = False,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Install a Python package with pip.

        Requires explicit confirmation when ``security.require_confirmation``
        is enabled in config.

        Args:
            package: The package name (e.g. "requests", "fastmcp>=2.0").
            version: Optional version specifier (e.g. "==2.31.0", ">=1.0").
            upgrade: If True, upgrade the package if already installed.
            confirm: Set to True to confirm this operation when required.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            install_package("requests", confirm=True)
            install_package("fastmcp", version=">=2.0", confirm=True)
            install_package("numpy", upgrade=True, confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager
        from utils.json_utils import confirmation_required

        pm = PermissionManager()
        if pm.requires_confirmation("install_package"):
            try:
                pm.assert_confirmed(action=f"pip install {package}", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"pip install {package}", tool="install_package")

        spec = f"{package}{version}" if version else package
        upgrade_flag = "--upgrade" if upgrade else ""
        command = f"{self._pip_cmd()} install {upgrade_flag} {spec}".strip()
        result = self._run_safe(command, tool_name="install_package")
        return self._shell_response(result, tool_name="install_package")

    @tool
    def uninstall_package(self, package: str, confirm: bool = False) -> dict[str, Any]:
        """
        Uninstall a Python package with pip.

        Requires explicit confirmation (passes --yes to pip to avoid interactive prompt).

        Args:
            package: The package name to uninstall.
            confirm: Set to True to confirm this destructive operation.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            uninstall_package("requests", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager
        from utils.json_utils import confirmation_required

        pm = PermissionManager()
        if pm.requires_confirmation("uninstall_package"):
            try:
                pm.assert_confirmed(action=f"pip uninstall {package}", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"pip uninstall {package}", tool="uninstall_package")

        command = f"{self._pip_cmd()} uninstall --yes {package}"
        result = self._run_safe(command, tool_name="uninstall_package")
        return self._shell_response(result, tool_name="uninstall_package")

    # ------------------------------------------------------------------
    # Virtual Environments
    # ------------------------------------------------------------------

    @tool
    def create_venv(self, path: str = ".venv") -> dict[str, Any]:
        """
        Create a new Python virtual environment.

        Args:
            path: Path for the virtual environment. Default: ".venv"
                  relative to the current working directory.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            create_venv()
            create_venv(".venv")
            create_venv("envs/myproject")
        """
        command = f'python -m venv "{path}"'
        result = self._run_safe(command, tool_name="create_venv")
        return self._shell_response(result, tool_name="create_venv")

    @tool
    def activate_venv(self, path: str = ".venv") -> dict[str, Any]:
        """
        Register a virtual environment as active in the current session.

        This does not "activate" the venv in a shell sense (which is a
        shell-level operation). Instead, it records the venv path in the
        session so that subsequent python_* and pip_* tool calls use the
        venv's interpreter and pip automatically.

        Args:
            path: Path to the virtual environment directory.

        Returns:
            A dict with keys: status, data (venv details).

        Examples:
            activate_venv()
            activate_venv(".venv")
            activate_venv("C:/projects/myapp/.venv")
        """
        from pathlib import Path

        from core.session import get_session
        from utils.json_utils import error as make_error
        from utils.json_utils import success

        session = get_session()
        venv_path = Path(path) if Path(path).is_absolute() else session.cwd / path
        venv_path = venv_path.resolve()

        if not venv_path.exists():
            return make_error(
                f"Virtual environment not found: {venv_path}. Run create_venv() first.",
                tool="activate_venv",
                code="NOT_FOUND",
            )

        py_exe = venv_path / "Scripts" / "python.exe"
        if not py_exe.exists():
            return make_error(
                f"Not a valid virtual environment (no Scripts/python.exe): {venv_path}",
                tool="activate_venv",
                code="INVALID_VENV",
            )

        session.set_active_venv(venv_path)
        logger.info("Session venv set to: %s", venv_path)

        return success(
            {
                "venv": str(venv_path),
                "python": str(py_exe),
                "active": True,
            },
            tool="activate_venv",
        )

    @tool
    def deactivate_venv(self) -> dict[str, Any]:
        """
        Deactivate the current session's virtual environment.

        After this call, python_* and pip_* tools will use the system
        Python interpreter.

        Returns:
            A dict with keys: status, data (confirmation).

        Examples:
            deactivate_venv()
        """
        from core.session import get_session
        from utils.json_utils import success

        session = get_session()
        old = session.active_venv
        session.set_active_venv(None)
        return success(
            {
                "previous_venv": str(old) if old else None,
                "active": False,
            },
            tool="deactivate_venv",
        )

    # ------------------------------------------------------------------
    # Script Execution
    # ------------------------------------------------------------------

    @tool
    def run_python_script(
        self,
        path: str,
        args: str = "",
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Execute a Python script file.

        The script must be within the workspace boundary. Uses the active
        virtual environment's Python if one is registered in the session.

        Args:
            path:    Path to the .py script (absolute or relative to cwd).
            args:    Optional command-line arguments to pass to the script.
            timeout: Maximum execution time in seconds. Default: 120.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            run_python_script("scripts/migrate.py")
            run_python_script("app.py", args="--port 8080")
        """
        from pathlib import Path

        from core.exceptions import WorkspaceViolationError
        from core.session import get_session
        from security.sandbox import WorkspaceSandbox
        from utils.json_utils import error as make_error
        from utils.json_utils import not_found

        session = get_session()
        sandbox = WorkspaceSandbox()

        try:
            script_path = sandbox.resolve_safe(
                Path(path) if Path(path).is_absolute() else session.cwd / path
            )
        except WorkspaceViolationError as exc:
            return make_error(str(exc), tool="run_python_script", code="WORKSPACE_VIOLATION")

        if not script_path.exists():
            return not_found(f"Script {script_path}", tool="run_python_script")

        command = f'{self._python_cmd()} "{script_path}" {args}'.strip()
        result = self._run_safe(
            command,
            timeout=max(1, min(timeout, 3600)),
            tool_name="run_python_script",
        )
        return self._shell_response(result, tool_name="run_python_script")
