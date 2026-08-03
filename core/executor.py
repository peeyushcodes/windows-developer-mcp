"""
Command execution pipeline for Windows Developer MCP.

The :class:`CommandExecutor` is the single entry point for all shell
command execution. Every command — regardless of which provider initiates
it — passes through this pipeline in strict order:

.. code-block:: text

    CommandExecutor.run(command)
        │
        ├── 1. CommandValidator.validate()
        │       → ValidationError on failure
        │
        ├── 2. PermissionManager.check_read_only()
        │       → ReadOnlyModeError on failure
        │
        ├── 3. AuditLogger.log_start()
        │
        ├── 4. ShellRunner.run()
        │       → ShellResult
        │
        ├── 5. Session.add_history()
        │
        └── 6. AuditLogger.log_result() → return ShellResult

No code outside this module should call ``subprocess`` directly.

Usage::

    from core.executor import CommandExecutor
    from core.context import RequestContext
    from utils.shell import Shell

    executor = CommandExecutor()
    ctx = RequestContext(tool_name="git_status")
    result = executor.run("git status", context=ctx)
    print(result.stdout)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.config import get_config
from core.exceptions import PermissionDeniedError, ValidationError
from core.session import Session, get_session
from security.logger import AuditLogger
from security.permissions import PermissionManager
from security.validator import CommandValidator
from utils.shell import Shell, ShellResult, ShellRunner

if TYPE_CHECKING:
    from pathlib import Path

    from core.context import RequestContext

logger = logging.getLogger(__name__)

# Module-level singleton instances — shared across all providers.
_validator = CommandValidator()
_permissions = PermissionManager()
_runner = ShellRunner()
_audit = AuditLogger()


class CommandExecutor:
    """
    Orchestrates the full command execution pipeline.

    Providers use this class (via :func:`get_executor`) to run shell
    commands. The executor applies validation, permission checks, audit
    logging, and session tracking automatically.

    Args:
        session: The session to record history in. Defaults to the global
                 session singleton if not provided.
    """

    def __init__(self, session: Session | None = None) -> None:
        self._session = session or get_session()

    def run(
        self,
        command: str,
        *,
        context: RequestContext,
        shell: Shell = Shell.POWERSHELL,
        cwd: Path | None = None,
        timeout: int | None = None,
        extra_env: dict[str, str] | None = None,
        skip_validation: bool = False,
    ) -> ShellResult:
        """
        Execute a shell command through the full security pipeline.

        Args:
            command:         The command string to execute.
            context:         Per-request context for logging and tracing.
            shell:           Shell backend to use.
            cwd:             Working directory override. Defaults to session cwd.
            timeout:         Timeout override in seconds. Defaults to config value.
            extra_env:       Additional environment variables for the subprocess.
            skip_validation: If ``True``, skip validation (internal use only).
                             Never expose this to external callers.

        Returns:
            A :class:`ShellResult` with the command output, exit code, and timing.

        Raises:
            ValidationError:     If the command fails validation.
            PermissionDeniedError: If the operation is blocked by permissions.
        """
        cfg = get_config()
        effective_cwd = cwd or self._session.cwd
        effective_timeout = timeout if timeout is not None else cfg.security.timeout
        effective_env = {**self._session.get_all_env(), **(extra_env or {})}

        # ------------------------------------------------------------------
        # Step 1 — Validate
        # ------------------------------------------------------------------
        if not skip_validation:
            validation = _validator.validate(command)
            if not validation.allowed:
                _audit.log_blocked(
                    context,
                    command=command,
                    reason=validation.reason,
                    code=validation.code,
                )
                raise ValidationError(validation.reason, code=validation.code)

        # ------------------------------------------------------------------
        # Step 2 — Permission Check
        # ------------------------------------------------------------------
        perm = _permissions.check_read_only(context.tool_name, command)
        if not perm.allowed:
            _audit.log_blocked(
                context,
                command=command,
                reason=perm.reason,
                code=perm.code,
            )
            raise PermissionDeniedError(perm.reason, code=perm.code)

        # ------------------------------------------------------------------
        # Step 3 — Audit: Log Start
        # ------------------------------------------------------------------
        _audit.log_start(
            context,
            command=command,
            cwd=effective_cwd,
            shell=str(shell),
        )

        # ------------------------------------------------------------------
        # Step 4 — Execute
        # ------------------------------------------------------------------
        result = _runner.run(
            command,
            shell=shell,
            cwd=effective_cwd,
            timeout=effective_timeout,
            extra_env=effective_env if effective_env else None,
            max_output=cfg.security.max_output_length,
        )

        # ------------------------------------------------------------------
        # Step 5 — Session History
        # ------------------------------------------------------------------
        self._session.add_history(
            command,
            tool=context.tool_name,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
        )

        # ------------------------------------------------------------------
        # Step 6 — Audit: Log Result
        # ------------------------------------------------------------------
        _audit.log_result(
            context,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            command=command,
            cwd=effective_cwd,
        )

        logger.debug(
            "[%s] %s → exit=%d (%dms)",
            context.tool_name,
            command[:80],
            result.exit_code,
            result.duration_ms,
        )

        return result

    def run_safe(
        self,
        command: str,
        *,
        context: RequestContext,
        shell: Shell = Shell.POWERSHELL,
        cwd: Path | None = None,
        timeout: int | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> ShellResult:
        """
        Execute a command and return a result without raising on security failures.

        Unlike :meth:`run`, this method catches :class:`ValidationError` and
        :class:`PermissionDeniedError` and returns them as failed
        :class:`ShellResult` objects.

        This is useful in providers that want to return structured error
        responses rather than propagating exceptions.

        Args:
            command:   The command string to execute.
            context:   Per-request context.
            shell:     Shell backend.
            cwd:       Working directory override.
            timeout:   Timeout override.
            extra_env: Additional environment variables.

        Returns:
            A :class:`ShellResult`. On security failure, the result will have
            ``exit_code=-1`` and the rejection reason in ``stderr``.
        """
        try:
            return self.run(
                command,
                context=context,
                shell=shell,
                cwd=cwd,
                timeout=timeout,
                extra_env=extra_env,
            )
        except (ValidationError, PermissionDeniedError) as exc:
            return ShellResult(
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                duration_ms=context.elapsed_ms,
                command=command,
                shell=shell,
            )


# ==============================================================================
# Module-Level Singleton
# ==============================================================================

_executor: CommandExecutor | None = None


def get_executor() -> CommandExecutor:
    """
    Return the global :class:`CommandExecutor` singleton.

    The executor is created lazily on first access, wiring up the global
    session, validator, permission manager, and audit logger.

    Returns:
        The application :class:`CommandExecutor` instance.
    """
    global _executor
    if _executor is None:
        _executor = CommandExecutor()
    return _executor


def reset_executor() -> None:
    """
    Clear the cached executor singleton.

    Intended for use in tests only.
    """
    global _executor
    _executor = None
