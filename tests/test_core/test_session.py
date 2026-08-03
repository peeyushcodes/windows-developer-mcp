"""Tests for the core.session module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from core.session import Session, get_session, reset_session

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def session(workspace_root: Path) -> Session:
    reset_session()
    s = get_session()
    s.change_directory(str(workspace_root))
    return s


class TestSessionCwd:
    def test_default_cwd_is_set(self, session: Session) -> None:
        assert session.cwd.is_dir()

    def test_change_directory_succeeds_for_existing_dir(
        self, session: Session, workspace_root: Path
    ) -> None:
        new_cwd = session.change_directory(str(workspace_root / "src"))
        assert new_cwd == (workspace_root / "src").resolve()
        assert session.cwd == (workspace_root / "src").resolve()

    def test_change_directory_raises_for_nonexistent(self, session: Session) -> None:
        with pytest.raises(FileNotFoundError):
            session.change_directory("/nonexistent/path/xyz")

    def test_change_directory_raises_for_file(self, session: Session, workspace_root: Path) -> None:
        with pytest.raises(NotADirectoryError):
            session.change_directory(str(workspace_root / "README.md"))


class TestSessionHistory:
    def test_history_is_empty_on_start(self, session: Session) -> None:
        assert session.get_history() == []

    def test_add_history_entry(self, session: Session) -> None:
        session.add_history("git status", tool="git_status", exit_code=0, duration_ms=50)
        history = session.get_history()
        assert len(history) == 1
        assert history[0]["command"] == "git status"
        assert history[0]["tool"] == "git_status"
        assert history[0]["exit_code"] == 0

    def test_history_respects_limit(self, session: Session) -> None:
        for i in range(10):
            session.add_history(f"cmd {i}", tool="test", exit_code=0, duration_ms=10)
        assert len(session.get_history(limit=5)) == 5

    def test_clear_history(self, session: Session) -> None:
        session.add_history("some command", tool="test", exit_code=0, duration_ms=10)
        session.clear_history()
        assert session.get_history() == []


class TestSessionEnv:
    def test_set_and_get_env(self, session: Session) -> None:
        session.set_env("MY_VAR", "my_value")
        assert session.get_env("MY_VAR") == "my_value"

    def test_get_env_returns_none_for_missing(self, session: Session) -> None:
        assert session.get_env("NONEXISTENT_VAR_12345") is None

    def test_get_all_env_returns_dict(self, session: Session) -> None:
        session.set_env("A", "1")
        session.set_env("B", "2")
        env = session.get_all_env()
        assert env["A"] == "1"
        assert env["B"] == "2"


class TestSessionVenv:
    def test_active_venv_is_none_by_default(self, session: Session) -> None:
        assert session.active_venv is None

    def test_set_active_venv(self, session: Session, workspace_root: Path) -> None:
        venv_path = workspace_root / ".venv"
        venv_path.mkdir(exist_ok=True)
        session.set_active_venv(venv_path)
        assert session.active_venv == venv_path

    def test_clear_active_venv(self, session: Session, workspace_root: Path) -> None:
        venv_path = workspace_root / ".venv"
        venv_path.mkdir(exist_ok=True)
        session.set_active_venv(venv_path)
        session.set_active_venv(None)
        assert session.active_venv is None


class TestSessionSingleton:
    def test_get_session_returns_same_instance(self) -> None:
        s1 = get_session()
        s2 = get_session()
        assert s1 is s2

    def test_reset_session_creates_new_instance(self) -> None:
        s1 = get_session()
        reset_session()
        s2 = get_session()
        assert s1 is not s2

    def test_to_dict_returns_serializable(self, session: Session) -> None:
        import json

        d = session.to_dict()
        # Should be JSON serializable
        json.dumps(d, default=str)
        assert "cwd" in d
        assert "started_at" in d
