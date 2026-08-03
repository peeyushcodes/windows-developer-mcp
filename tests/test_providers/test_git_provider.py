"""Unit tests for GitProvider."""

from pathlib import Path

import pytest

from core.session import get_session, reset_session
from providers.git import GitProvider


@pytest.fixture(autouse=True)
def setup_session():
    reset_session()
    session = get_session()
    session.change_directory(str(Path.cwd()))
    yield


class TestGitProvider:
    def test_git_status(self):
        provider = GitProvider()
        res = provider.git_status()
        assert res["status"] in ("success", "error")
        assert "exit_code" in res

    def test_git_branch(self):
        provider = GitProvider()
        res = provider.git_branch()
        assert res["status"] in ("success", "error")
