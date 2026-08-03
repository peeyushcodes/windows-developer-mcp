"""Unit tests for TerminalProvider."""

from pathlib import Path

import pytest

from core.session import get_session, reset_session
from providers.terminal import TerminalProvider


@pytest.fixture(autouse=True)
def setup_session():
    reset_session()
    session = get_session()
    session.change_directory(str(Path.cwd()))
    yield


class TestTerminalProvider:
    def test_run_powershell(self):
        provider = TerminalProvider()
        res = provider.run_powershell("Write-Host 'hello_terminal'")
        assert res["status"] == "success"
        assert "hello_terminal" in res["output"]

    def test_get_working_directory(self):
        provider = TerminalProvider()
        res = provider.get_working_directory()
        assert res["status"] == "success"
        assert "cwd" in res["data"]

    def test_get_session_info(self):
        provider = TerminalProvider()
        res = provider.get_session_info()
        assert res["status"] == "success"
        assert "started_at" in res["data"]
        assert "cwd" in res["data"]
