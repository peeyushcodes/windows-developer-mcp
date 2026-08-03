"""
Safe subprocess execution utilities for Windows Developer MCP.

This module provides the :class:`ShellRunner` class, which wraps Python's
``subprocess`` module with:

- Explicit shell selection (PowerShell or CMD)
- Configurable timeouts
- Session environment variable merging
- Structured :class:`ShellResult` return values
- No shell=True (prevents shell injection)

All subprocess calls must go through this module. Direct ``subprocess``
usage elsewhere in the codebase is prohibited.

Usage::

    from utils.shell import ShellRunner, Shell

    runner = ShellRunner()
    result = runner.run("git status", shell=Shell.POWERSHELL, cwd=Path("/projects/myapp"))
    if result.succeeded:
        print(result.stdout)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging
import os
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class Shell(StrEnum):
    """Available shell backends for command execution."""

    POWERSHELL = "powershell"
    CMD = "cmd"


@dataclass
class ShellResult:
    """
    Structured result from a subprocess execution.

    Attributes:
        stdout:      Standard output, stripped of trailing whitespace.
        stderr:      Standard error, stripped of trailing whitespace.
        exit_code:   Process return code (0 = success).
        duration_ms: Wall-clock execution time in milliseconds.
        command:     The original command string.
        shell:       The shell backend used.
    """

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    command: str
    shell: Shell

    @property
    def succeeded(self) -> bool:
        """True if the exit code is 0."""
        return self.exit_code == 0

    @property
    def output(self) -> str:
        """
        Return the most useful output string.

        Returns ``stdout`` if present, otherwise ``stderr``.
        """
        return self.stdout if self.stdout else self.stderr

    @property
    def combined(self) -> str:
        """Return stdout and stderr concatenated with a newline separator."""
        parts = [p for p in (self.stdout, self.stderr) if p]
        return "\n".join(parts)

    def to_dict(self) -> dict[str, str | int | bool]:
        """Return a JSON-serialisable representation."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "succeeded": self.succeeded,
            "command": self.command,
            "shell": str(self.shell),
        }


class ShellRunner:
    """
    Safe subprocess wrapper for PowerShell and CMD execution.

    :class:`ShellRunner` never uses ``shell=True``. Instead it builds an
    explicit argument list for the chosen shell binary, which eliminates
    most shell injection vectors at the OS level.

    Each instance is stateless and may be shared across threads.
    """

    # PowerShell arguments applied to every invocation.
    _PS_BASE_ARGS: tuple[str, ...] = (
        "powershell",
        "-NoProfile",       # skip user profile (faster startup)
        "-NonInteractive",  # suppress interactive prompts
        "-ExecutionPolicy", "Bypass",  # allow unsigned scripts in this process
        "-Command",
    )

    # CMD arguments applied to every invocation.
    _CMD_BASE_ARGS: tuple[str, ...] = ("cmd", "/C")

    def run(
        self,
        command: str,
        *,
        shell: Shell = Shell.POWERSHELL,
        cwd: Path | None = None,
        timeout: int = 60,
        extra_env: dict[str, str] | None = None,
        max_output: int = 50_000,
    ) -> ShellResult:
        """
        Execute ``command`` in the specified shell and return a :class:`ShellResult`.

        Args:
            command:    The command string to execute.
            shell:      Which shell backend to use (:attr:`Shell.POWERSHELL` or
                        :attr:`Shell.CMD`).
            cwd:        Working directory for the subprocess. Defaults to the
                        current process working directory.
            timeout:    Maximum seconds before the process is killed.
            extra_env:  Additional environment variables merged on top of the
                        inherited process environment.
            max_output: Maximum characters retained from stdout and stderr.

        Returns:
            A :class:`ShellResult` with stdout, stderr, exit code, and timing.

        Raises:
            subprocess.TimeoutExpired: Never — this is caught and returned as
                a failed :class:`ShellResult` with exit_code=-1.
        """
        args = self._build_args(command, shell)
        env = self._build_env(extra_env)
        cwd_str = str(cwd) if cwd else None

        logger.debug("Executing via %s: %r (cwd=%s, timeout=%ds)", shell, command, cwd_str, timeout)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd_str,
                env=env,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            stdout = self._truncate(proc.stdout.strip(), max_output)
            stderr = self._truncate(proc.stderr.strip(), max_output)

            return ShellResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                command=command,
                shell=shell,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.warning("Command timed out after %ds: %r", timeout, command)
            return ShellResult(
                stdout="",
                stderr=f"Command timed out after {timeout} seconds.",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command,
                shell=shell,
            )

        except FileNotFoundError:
            # Shell binary not found on PATH
            duration_ms = int((time.monotonic() - start) * 1000)
            binary = "powershell" if shell == Shell.POWERSHELL else "cmd"
            logger.error("Shell binary not found: %s", binary)
            return ShellResult(
                stdout="",
                stderr=f"Shell not found: {binary!r}. Ensure it is on PATH.",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command,
                shell=shell,
            )

        except OSError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception("OS error during command execution: %s", exc)
            return ShellResult(
                stdout="",
                stderr=f"OS error: {exc}",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command,
                shell=shell,
            )

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _build_args(self, command: str, shell: Shell) -> list[str]:
        """Build the subprocess argument list for the given shell."""
        if shell == Shell.POWERSHELL:
            return [*self._PS_BASE_ARGS, command]
        return [*self._CMD_BASE_ARGS, command]

    @staticmethod
    def _build_env(extra_env: dict[str, str] | None) -> dict[str, str]:
        """Merge ``extra_env`` on top of the inherited process environment."""
        env = dict(os.environ)
        if extra_env:
            env.update(extra_env)
        return env

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate ``text`` to ``max_len`` characters with a notice."""
        if len(text) <= max_len:
            return text
        notice = f"\n\n[Output truncated: showing {max_len:,} of {len(text):,} characters]"
        return text[:max_len] + notice
