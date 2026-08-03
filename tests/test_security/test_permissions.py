"""Tests for security.permissions module."""

from __future__ import annotations

import pytest

from core.exceptions import ConfirmationRequiredError, ReadOnlyModeError
from security.permissions import PermissionManager


@pytest.fixture()
def pm() -> PermissionManager:
    return PermissionManager()


class TestReadOnlyMode:
    def test_write_allowed_when_not_readonly(
        self, pm: PermissionManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config
        monkeypatch.setattr(get_config().workspace, "read_only", False)
        result = pm.check_read_only("write_file")
        assert result.allowed

    def test_write_blocked_in_readonly_mode(
        self, pm: PermissionManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config
        monkeypatch.setattr(get_config().workspace, "read_only", True)
        result = pm.check_read_only("write_file")
        assert not result.allowed
        assert result.code == "READ_ONLY_MODE"

    def test_read_operations_allowed_in_readonly(
        self, pm: PermissionManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config
        monkeypatch.setattr(get_config().workspace, "read_only", True)
        result = pm.check_read_only("read_file")
        assert result.allowed

    def test_assert_not_read_only_raises_in_readonly(
        self, pm: PermissionManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config
        monkeypatch.setattr(get_config().workspace, "read_only", True)
        with pytest.raises(ReadOnlyModeError):
            pm.assert_not_read_only("write_file")


class TestConfirmation:
    def test_confirmation_required_for_known_destructive_tool(
        self, pm: PermissionManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config
        monkeypatch.setattr(get_config().security, "require_confirmation", True)
        assert pm.requires_confirmation("delete_file") is True
        assert pm.requires_confirmation("git_push") is True
        assert pm.requires_confirmation("git_commit") is True

    def test_confirmation_not_required_when_disabled(
        self, pm: PermissionManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config
        monkeypatch.setattr(get_config().security, "require_confirmation", False)
        assert pm.requires_confirmation("delete_file") is False

    def test_confirmation_not_required_for_safe_tools(
        self, pm: PermissionManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from core.config import get_config
        monkeypatch.setattr(get_config().security, "require_confirmation", True)
        assert pm.requires_confirmation("git_status") is False
        assert pm.requires_confirmation("read_file") is False
        assert pm.requires_confirmation("list_packages") is False

    def test_assert_confirmed_passes_when_true(self, pm: PermissionManager) -> None:
        pm.assert_confirmed(action="test action", confirm=True)  # should not raise

    def test_assert_confirmed_raises_when_false(self, pm: PermissionManager) -> None:
        with pytest.raises(ConfirmationRequiredError):
            pm.assert_confirmed(action="test action", confirm=False)
