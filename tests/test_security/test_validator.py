"""
Tests for the security.validator module.

Covers all validation stages:
- Length limit
- Allowlist enforcement
- Dangerous pattern matching
- Extra pattern blocking
- Injection detection
"""

from __future__ import annotations

import pytest

from security.validator import _MAX_COMMAND_LENGTH, CommandValidator, ValidationResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def validator() -> CommandValidator:
    return CommandValidator()


# ---------------------------------------------------------------------------
# Length Check
# ---------------------------------------------------------------------------


class TestLengthCheck:
    def test_normal_command_passes(self, validator: CommandValidator) -> None:
        result = validator.validate("git status")
        assert result.allowed

    def test_command_at_exact_limit_passes(self, validator: CommandValidator) -> None:
        command = "a" * _MAX_COMMAND_LENGTH
        result = validator.validate(command)
        assert result.allowed

    def test_command_exceeding_limit_is_rejected(self, validator: CommandValidator) -> None:
        command = "a" * (_MAX_COMMAND_LENGTH + 1)
        result = validator.validate(command)
        assert not result.allowed
        assert result.code == "COMMAND_TOO_LONG"

    def test_empty_command_passes(self, validator: CommandValidator) -> None:
        result = validator.validate("")
        assert result.allowed


# ---------------------------------------------------------------------------
# Dangerous Pattern Matching
# ---------------------------------------------------------------------------

DANGEROUS_CASES = [
    ("shutdown /s /t 0", "shutdown"),
    ("format c:", "format_disk"),
    ("del /f /s /q C:\\*", "mass_delete"),
    ("net user admin /add", "net_user"),
    ("reg delete HKLM", "reg_delete"),
    ("powershell -enc abc", "encoded_powershell"),
    ("Set-ExecutionPolicy Bypass", "execution_policy"),
    ("Invoke-Expression 'cmd'", "invoke_expression"),
    ("Stop-Service windefend", "stop_service"),
]


class TestDangerousPatterns:
    @pytest.mark.parametrize("command,expected_pattern", DANGEROUS_CASES)
    def test_dangerous_commands_are_blocked(
        self, validator: CommandValidator, command: str, expected_pattern: str
    ) -> None:
        result = validator.validate(command)
        assert not result.allowed, f"Expected {command!r} to be blocked"
        assert result.code == "DANGEROUS_COMMAND"
        assert result.matched_pattern == expected_pattern

    def test_safe_git_command_passes(self, validator: CommandValidator) -> None:
        assert validator.validate("git status").allowed
        assert validator.validate("git log --oneline -5").allowed
        assert validator.validate("git diff --staged").allowed

    def test_safe_python_command_passes(self, validator: CommandValidator) -> None:
        assert validator.validate("python --version").allowed
        assert validator.validate("pip list").allowed
        assert validator.validate("pip install requests").allowed

    def test_safe_node_command_passes(self, validator: CommandValidator) -> None:
        assert validator.validate("node --version").allowed
        assert validator.validate("npm list").allowed


# ---------------------------------------------------------------------------
# Allowlist Enforcement
# ---------------------------------------------------------------------------


class TestAllowlist:
    def test_allowlisted_command_passes(
        self, validator: CommandValidator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config

        cfg = get_config()
        monkeypatch.setattr(cfg.security, "command_allowlist", ["git", "python"])
        assert validator.validate("git status").allowed
        assert validator.validate("python --version").allowed

    def test_non_allowlisted_command_fails(
        self, validator: CommandValidator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config

        cfg = get_config()
        monkeypatch.setattr(cfg.security, "command_allowlist", ["git"])
        result = validator.validate("python --version")
        assert not result.allowed
        assert result.code == "NOT_ALLOWLISTED"

    def test_allowlist_is_case_insensitive(
        self, validator: CommandValidator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config

        cfg = get_config()
        monkeypatch.setattr(cfg.security, "command_allowlist", ["GIT"])
        assert validator.validate("git status").allowed
        assert validator.validate("Git Status").allowed


# ---------------------------------------------------------------------------
# Extra Blocked Patterns
# ---------------------------------------------------------------------------


class TestExtraPatterns:
    def test_extra_pattern_blocks_command(
        self, validator: CommandValidator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config

        cfg = get_config()
        monkeypatch.setattr(cfg.security, "extra_blocked_patterns", [r"my_secret_tool"])
        result = validator.validate("my_secret_tool --run")
        assert not result.allowed
        assert result.code == "CUSTOM_BLOCKED_PATTERN"

    def test_invalid_extra_pattern_is_skipped_gracefully(
        self, validator: CommandValidator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config

        cfg = get_config()
        # Deliberately invalid regex — should not crash
        monkeypatch.setattr(cfg.security, "extra_blocked_patterns", ["[invalid("])
        result = validator.validate("some command")
        # Should still allow (invalid pattern is skipped with warning)
        assert result.allowed


# ---------------------------------------------------------------------------
# Injection Detection
# ---------------------------------------------------------------------------


class TestInjectionDetection:
    def test_backtick_subshell_is_blocked(self, validator: CommandValidator) -> None:
        result = validator.validate("echo `rm -rf /`")
        assert not result.allowed
        assert result.code == "COMMAND_INJECTION"

    def test_dollar_paren_subshell_is_blocked(self, validator: CommandValidator) -> None:
        result = validator.validate("echo $(rm -rf /)")
        assert not result.allowed
        assert result.code == "COMMAND_INJECTION"

    def test_semicolon_rm_is_blocked(self, validator: CommandValidator) -> None:
        result = validator.validate("ls; rm /tmp/file")
        assert not result.allowed
        assert result.code == "COMMAND_INJECTION"

    def test_pipe_rm_is_blocked(self, validator: CommandValidator) -> None:
        result = validator.validate("cat file | rm something")
        assert not result.allowed
        assert result.code == "COMMAND_INJECTION"


# ---------------------------------------------------------------------------
# validate_or_raise
# ---------------------------------------------------------------------------


class TestValidateOrRaise:
    def test_safe_command_does_not_raise(self, validator: CommandValidator) -> None:
        validator.validate_or_raise("git status")  # should not raise

    def test_dangerous_command_raises_validation_error(self, validator: CommandValidator) -> None:
        from core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            validator.validate_or_raise("shutdown /s /t 0")


# ---------------------------------------------------------------------------
# ValidationResult helpers
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_permit_factory(self) -> None:
        r = ValidationResult.permit()
        assert r.allowed is True
        assert r.reason == ""

    def test_deny_factory(self) -> None:
        r = ValidationResult.deny("bad command", code="TEST_CODE", pattern="test")
        assert r.allowed is False
        assert r.code == "TEST_CODE"
        assert r.matched_pattern == "test"
