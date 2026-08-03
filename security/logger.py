"""
Structured audit logging for Windows Developer MCP.

The :class:`AuditLogger` writes one JSON Lines record per command execution
to a rotating log file. Every record is machine-readable and importable
into log aggregation tools (Splunk, ELK, Loki, etc.).

Log Record Schema::

    {
        "ts":          "2026-08-03T00:00:00.000Z",  # ISO 8601 UTC
        "request_id":  "abc12345",
        "tool":        "git_status",
        "command":     "git status",
        "cwd":         "C:/projects/myapp",
        "user":        "developer",
        "shell":       "powershell",
        "exit_code":   0,
        "duration_ms": 142,
        "error":       null
    }

Usage::

    from security.logger import AuditLogger

    audit = AuditLogger()
    audit.log_start(ctx, command="git status", cwd=Path("/projects"))
    audit.log_result(ctx, exit_code=0, duration_ms=142)
    audit.log_error(ctx, error="fatal: not a git repository")
"""

from __future__ import annotations

from datetime import UTC, datetime
import getpass
import json
import logging
import logging.handlers
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.config import get_config
from utils.paths import ensure_directory

if TYPE_CHECKING:
    from core.context import RequestContext

# Module-level standard logger (for meta-logging — logging about logging).
_meta = logging.getLogger(__name__)


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _current_user() -> str:
    """Return the current OS username, falling back gracefully."""
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


class AuditLogger:
    """
    Structured JSON Lines audit logger for MCP command executions.

    Each instance creates (or re-opens) a rotating log file under the
    configured ``logging.log_dir`` directory. The logger is thread-safe
    because :class:`logging.handlers.RotatingFileHandler` uses an internal
    lock.

    The audit log is append-only. Records are never modified or deleted
    by the application.
    """

    def __init__(self) -> None:
        self._logger: logging.Logger | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_start(
        self,
        ctx: RequestContext,
        *,
        command: str,
        cwd: Path,
        shell: str = "powershell",
    ) -> None:
        """
        Write an audit record at the start of a command execution.

        Args:
            ctx:     The :class:`RequestContext` for this request.
            command: The command about to be executed.
            cwd:     The working directory for the command.
            shell:   The shell backend being used.
        """
        record = self._build_record(
            ctx,
            command=command,
            cwd=cwd,
            shell=shell,
            exit_code=None,
            duration_ms=None,
            error=None,
            event="start",
        )
        self._write(record)

    def log_result(
        self,
        ctx: RequestContext,
        *,
        exit_code: int,
        duration_ms: int,
        command: str = "",
        cwd: Path | None = None,
    ) -> None:
        """
        Write an audit record after a command completes.

        Args:
            ctx:         The :class:`RequestContext` for this request.
            exit_code:   The process return code.
            duration_ms: Total execution time in milliseconds.
            command:     The command that was executed.
            cwd:         The working directory used.
        """
        record = self._build_record(
            ctx,
            command=command,
            cwd=cwd or Path(),
            shell="",
            exit_code=exit_code,
            duration_ms=duration_ms,
            error=None,
            event="result",
        )
        self._write(record)

    def log_error(
        self,
        ctx: RequestContext,
        *,
        error: str,
        command: str = "",
        cwd: Path | None = None,
    ) -> None:
        """
        Write an audit record when a command fails with an exception.

        Args:
            ctx:     The :class:`RequestContext` for this request.
            error:   The error message or exception string.
            command: The command that was being executed.
            cwd:     The working directory used.
        """
        record = self._build_record(
            ctx,
            command=command,
            cwd=cwd or Path(),
            shell="",
            exit_code=-1,
            duration_ms=ctx.elapsed_ms,
            error=error,
            event="error",
        )
        self._write(record)

    def log_blocked(
        self,
        ctx: RequestContext,
        *,
        command: str,
        reason: str,
        code: str,
    ) -> None:
        """
        Write an audit record when a command is blocked by the security layer.

        Args:
            ctx:     The :class:`RequestContext` for this request.
            command: The rejected command string.
            reason:  Human-readable rejection reason.
            code:    Machine-readable rejection code.
        """
        record = self._build_record(
            ctx,
            command=command,
            cwd=Path(),
            shell="",
            exit_code=None,
            duration_ms=None,
            error=None,
            event="blocked",
        )
        record["blocked_reason"] = reason
        record["blocked_code"] = code
        self._write(record)

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _build_record(
        self,
        ctx: RequestContext,
        *,
        command: str,
        cwd: Path,
        shell: str,
        exit_code: int | None,
        duration_ms: int | None,
        error: str | None,
        event: str,
    ) -> dict[str, Any]:
        """Construct a log record dict from the given parameters."""
        return {
            "ts": _utc_now(),
            "event": event,
            "request_id": ctx.request_id,
            "tool": ctx.tool_name,
            "command": command,
            "cwd": str(cwd),
            "user": _current_user(),
            "shell": shell,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "error": error,
        }

    def _write(self, record: dict[str, Any]) -> None:
        """Serialise and write a record to the audit log file."""
        try:
            line = json.dumps(record, default=str, ensure_ascii=False)
            self._get_logger().info(line)
        except Exception as exc:
            _meta.error("Failed to write audit log record: %s", exc)

    def _get_logger(self) -> logging.Logger:
        """Return (and lazily initialise) the underlying file logger."""
        if self._logger is not None:
            return self._logger

        cfg = get_config()
        log_dir = ensure_directory(Path(cfg.logging.log_dir))
        log_file = log_dir / "audit.jsonl"

        # Create a dedicated logger so we don't pollute the root logger.
        inner = logging.getLogger("mcp.audit")
        inner.setLevel(logging.INFO)
        inner.propagate = False  # do not bubble up to root logger

        if not inner.handlers:
            handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=cfg.logging.max_log_size_mb * 1024 * 1024,
                backupCount=cfg.logging.backup_count,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            inner.addHandler(handler)

        self._logger = inner
        _meta.info("Audit log initialised at %s", log_file)
        return self._logger


# ==============================================================================
# Application-Level Logging Setup
# ==============================================================================


def configure_logging() -> None:
    """
    Configure the root Python logger for the application.

    Sets the log level and output format from the application config.
    Idempotent — safe to call multiple times.

    Call this once at application startup, before creating any providers.
    """
    cfg = get_config()
    level = getattr(logging, cfg.logging.level, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.getLogger("mcp.audit").propagate = False
    logging.getLogger(__name__).info(
        "Application logging configured: level=%s", cfg.logging.level
    )
