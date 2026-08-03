"""
Command validation pipeline for Windows Developer MCP.

The :class:`CommandValidator` is the first gate in the execution pipeline.
Every command passes through it before reaching the permission manager or
executor.

Validation steps (in order):
1. Length check — reject absurdly long commands.
2. Allowlist check — if configured, only matching commands pass.
3. Dangerous pattern check — reject against :data:`DANGEROUS_PATTERNS`.
4. Extra patterns check — reject against user-configured extra patterns.
5. Injection pattern check — detect common shell injection characters.

Usage::

    from security.validator import CommandValidator

    validator = CommandValidator()
    result = validator.validate("git status")
    if not result.allowed:
        print(f"Blocked: {result.reason}")
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from core.config import get_config
from core.exceptions import ValidationError
from security.dangerous_commands import (
    DangerousPattern,
    get_patterns,
)

logger = logging.getLogger(__name__)

# Maximum command length in characters. Prevents DoS via extremely long strings.
_MAX_COMMAND_LENGTH: int = 8_192

# Shell injection patterns that indicate potential command chaining or injection.
# These are heuristic — they may produce false positives for legitimate commands,
# so they are checked last and only when no allowlist is configured.
_INJECTION_PATTERNS: tuple[str, ...] = (
    r";\s*rm\b",  # ; rm
    r";\s*del\b",  # ; del
    r";\s*format\b",  # ; format
    r"\|\s*rm\b",  # | rm
    r"`[^`]+`",  # backtick subshell
    r"\$\([^)]+\)",  # $(command) subshell
    r"&&\s*(rm|del|format)",  # && followed by dangerous command
    r"\|\|\s*(rm|del|format)",  # || followed by dangerous command
)

_COMPILED_INJECTION: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS
)


# ==============================================================================
# Validation Result
# ==============================================================================


@dataclass
class ValidationResult:
    """
    The outcome of a single command validation run.

    Attributes:
        allowed:         ``True`` if the command passed all checks.
        reason:          Human-readable explanation if ``allowed`` is ``False``.
        code:            Machine-readable error code if ``allowed`` is ``False``.
        matched_pattern: Name of the :class:`DangerousPattern` that matched,
                         or empty string.
        severity:        Severity level of the matched pattern, or empty string.
    """

    allowed: bool
    reason: str = ""
    code: str = ""
    matched_pattern: str = ""
    severity: str = ""

    @classmethod
    def permit(cls) -> ValidationResult:
        """Construct a passing result."""
        return cls(allowed=True)

    @classmethod
    def deny(
        cls,
        reason: str,
        *,
        code: str = "VALIDATION_ERROR",
        pattern: str = "",
        severity: str = "",
    ) -> ValidationResult:
        """Construct a failing result."""
        return cls(
            allowed=False,
            reason=reason,
            code=code,
            matched_pattern=pattern,
            severity=severity,
        )


# ==============================================================================
# Validator
# ==============================================================================


class CommandValidator:
    """
    Multi-step command validation pipeline.

    Each :meth:`validate` call runs the command through a series of checks
    and returns a :class:`ValidationResult`. The validator reads configuration
    from :func:`core.config.get_config` on each call so that config changes
    (in tests) are reflected immediately.

    This class is stateless and thread-safe; a single instance may be shared
    across the entire application.
    """

    def validate(self, command: str) -> ValidationResult:
        """
        Validate ``command`` through all security checks.

        Args:
            command: The raw command string to validate.

        Returns:
            A :class:`ValidationResult` indicating whether the command is
            allowed and, if not, why.
        """
        cfg = get_config()

        # Step 1 — Length limit
        result = self._check_length(command)
        if not result.allowed:
            logger.warning("Command rejected (length): %d chars", len(command))
            return result

        # Step 2 — Allowlist (if configured, acts as an exclusive filter)
        if cfg.security.command_allowlist:
            result = self._check_allowlist(command, cfg.security.command_allowlist)
            if not result.allowed:
                logger.warning("Command rejected (allowlist): %r", command[:120])
                return result

        # Step 3 — Dangerous patterns (built-in)
        result = self._check_dangerous_patterns(command, get_patterns())
        if not result.allowed:
            logger.warning(
                "Command rejected (dangerous pattern=%r, severity=%s): %r",
                result.matched_pattern,
                result.severity,
                command[:120],
            )
            return result

        # Step 4 — Extra user-configured patterns
        if cfg.security.extra_blocked_patterns:
            result = self._check_extra_patterns(command, cfg.security.extra_blocked_patterns)
            if not result.allowed:
                logger.warning("Command rejected (extra pattern): %r", command[:120])
                return result

        # Step 5 — Injection heuristics (only when no allowlist is active)
        if not cfg.security.command_allowlist:
            result = self._check_injection(command)
            if not result.allowed:
                logger.warning("Command rejected (injection): %r", command[:120])
                return result

        logger.debug("Command validated OK: %r", command[:120])
        return ValidationResult.permit()

    def validate_or_raise(self, command: str) -> None:
        """
        Validate ``command`` and raise :class:`ValidationError` on failure.

        Args:
            command: The raw command string to validate.

        Raises:
            ValidationError: If the command fails any validation check.
        """
        result = self.validate(command)
        if not result.allowed:
            raise ValidationError(result.reason, code=result.code)

    # ------------------------------------------------------------------
    # Private Check Methods
    # ------------------------------------------------------------------

    @staticmethod
    def _check_length(command: str) -> ValidationResult:
        """Reject commands exceeding the maximum length."""
        if len(command) > _MAX_COMMAND_LENGTH:
            return ValidationResult.deny(
                f"Command too long: {len(command):,} characters (max {_MAX_COMMAND_LENGTH:,}).",
                code="COMMAND_TOO_LONG",
            )
        return ValidationResult.permit()

    @staticmethod
    def _check_allowlist(command: str, allowlist: list[str]) -> ValidationResult:
        """
        Return denied unless the command starts with an allowlisted prefix.

        Comparison is case-insensitive.
        """
        cmd_lower = command.strip().lower()
        for allowed_prefix in allowlist:
            if cmd_lower.startswith(allowed_prefix.lower()):
                return ValidationResult.permit()
        return ValidationResult.deny(
            f"Command is not on the allowlist. Allowed prefixes: {allowlist!r}",
            code="NOT_ALLOWLISTED",
        )

    @staticmethod
    def _check_dangerous_patterns(
        command: str,
        patterns: tuple[DangerousPattern, ...],
    ) -> ValidationResult:
        """Check the command against every registered dangerous pattern."""
        for pattern in patterns:
            if pattern.matches(command):
                return ValidationResult.deny(
                    f"Blocked: {pattern.description} "
                    f"(pattern: {pattern.name!r}, severity: {pattern.severity})",
                    code="DANGEROUS_COMMAND",
                    pattern=pattern.name,
                    severity=str(pattern.severity),
                )
        return ValidationResult.permit()

    @staticmethod
    def _check_extra_patterns(
        command: str,
        extra_patterns: list[str],
    ) -> ValidationResult:
        """Check the command against user-configured extra blocked patterns."""
        for raw_pattern in extra_patterns:
            try:
                if re.search(raw_pattern, command, re.IGNORECASE):
                    return ValidationResult.deny(
                        f"Blocked by custom pattern: {raw_pattern!r}",
                        code="CUSTOM_BLOCKED_PATTERN",
                        pattern=raw_pattern,
                    )
            except re.error as exc:
                logger.warning("Invalid extra_blocked_pattern %r: %s", raw_pattern, exc)
        return ValidationResult.permit()

    @staticmethod
    def _check_injection(command: str) -> ValidationResult:
        """Heuristic check for common shell injection patterns."""
        for compiled in _COMPILED_INJECTION:
            match = compiled.search(command)
            if match:
                return ValidationResult.deny(
                    f"Potential command injection detected near: {match.group()!r}",
                    code="COMMAND_INJECTION",
                )
        return ValidationResult.permit()
