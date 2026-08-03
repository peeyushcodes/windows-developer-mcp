"""
Custom exception hierarchy for Windows Developer MCP.

Design principles:
- Every failure mode has a dedicated exception class.
- All exceptions carry a human-readable ``message`` and a machine-readable ``code``.
- Callers catch specific exceptions, not bare ``Exception``.
- HTTP-style status codes are included for structured API responses.
"""

from __future__ import annotations


class MCPError(Exception):
    """
    Base exception for all Windows Developer MCP errors.

    All custom exceptions inherit from this class so callers can catch
    either specific errors or the entire MCP error hierarchy with a single
    ``except MCPError`` clause.
    """

    code: str = "MCP_ERROR"
    status: int = 500

    def __init__(self, message: str, *, code: str | None = None) -> None:
        """
        Initialise the exception.

        Args:
            message: Human-readable description of the error.
            code:    Optional machine-readable error code override.
                     Defaults to the class-level ``code`` attribute.
        """
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code

    def to_dict(self) -> dict[str, str | int]:
        """Return a JSON-serialisable representation of the error."""
        return {
            "error": self.code,
            "message": self.message,
            "status": self.status,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# ==============================================================================
# Validation Errors
# ==============================================================================


class ValidationError(MCPError):
    """Raised when a command fails pre-execution validation."""

    code = "VALIDATION_ERROR"
    status = 400


class CommandInjectionError(ValidationError):
    """Raised when a potential command injection pattern is detected."""

    code = "COMMAND_INJECTION"
    status = 400


class DangerousCommandError(ValidationError):
    """Raised when a known dangerous command is matched."""

    code = "DANGEROUS_COMMAND"
    status = 403

    def __init__(self, message: str, *, pattern_name: str = "", severity: str = "") -> None:
        super().__init__(message)
        self.pattern_name = pattern_name
        self.severity = severity


# ==============================================================================
# Permission Errors
# ==============================================================================


class PermissionDeniedError(MCPError):
    """Raised when an operation is forbidden by the permission model."""

    code = "PERMISSION_DENIED"
    status = 403


class ReadOnlyModeError(PermissionDeniedError):
    """Raised when a write operation is attempted in read-only mode."""

    code = "READ_ONLY_MODE"
    status = 403


class WorkspaceViolationError(PermissionDeniedError):
    """Raised when a path escapes the configured workspace boundary."""

    code = "WORKSPACE_VIOLATION"
    status = 403

    def __init__(self, message: str, *, path: str = "") -> None:
        super().__init__(message)
        self.path = path


class ConfirmationRequiredError(PermissionDeniedError):
    """Raised when a destructive command requires explicit confirmation."""

    code = "CONFIRMATION_REQUIRED"
    status = 403


# ==============================================================================
# Execution Errors
# ==============================================================================


class ExecutionError(MCPError):
    """Raised when command execution fails at the OS level."""

    code = "EXECUTION_ERROR"
    status = 500

    def __init__(self, message: str, *, exit_code: int = -1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class TimeoutError(ExecutionError):
    """Raised when a command exceeds the configured timeout."""

    code = "TIMEOUT"
    status = 408

    def __init__(self, message: str, *, timeout_seconds: int = 0) -> None:
        super().__init__(message, exit_code=-1)
        self.timeout_seconds = timeout_seconds


class ProcessError(ExecutionError):
    """Raised when the spawned process itself reports an error."""

    code = "PROCESS_ERROR"
    status = 500


# ==============================================================================
# Configuration Errors
# ==============================================================================


class ConfigurationError(MCPError):
    """Raised when the application configuration is invalid or missing."""

    code = "CONFIGURATION_ERROR"
    status = 500


# ==============================================================================
# Provider Errors
# ==============================================================================


class ProviderError(MCPError):
    """Base class for errors originating within a provider."""

    code = "PROVIDER_ERROR"
    status = 500

    def __init__(self, message: str, *, provider: str = "") -> None:
        super().__init__(message)
        self.provider = provider


class ProviderNotFoundError(ProviderError):
    """Raised when a requested provider is not registered."""

    code = "PROVIDER_NOT_FOUND"
    status = 404


class ProviderDisabledError(ProviderError):
    """Raised when an operation targets a disabled provider."""

    code = "PROVIDER_DISABLED"
    status = 503


# ==============================================================================
# Tool Errors
# ==============================================================================


class ToolError(MCPError):
    """Raised when a specific MCP tool encounters an operational failure."""

    code = "TOOL_ERROR"
    status = 500

    def __init__(self, message: str, *, tool: str = "") -> None:
        super().__init__(message)
        self.tool = tool


class NotFoundError(ToolError):
    """Raised when a requested resource (file, repo, package) does not exist."""

    code = "NOT_FOUND"
    status = 404


class ExternalServiceError(ToolError):
    """Raised when an external service (GitHub API, Docker daemon) is unreachable."""

    code = "EXTERNAL_SERVICE_ERROR"
    status = 502
