"""Unit tests for WindowsProvider."""

from pathlib import Path

import pytest

from core.session import get_session, reset_session
from providers.windows import WindowsProvider


@pytest.fixture(autouse=True)
def setup_session():
    reset_session()
    session = get_session()
    session.change_directory(str(Path.cwd()))
    yield


class TestWindowsProvider:
    def test_system_info(self):
        provider = WindowsProvider()
        res = provider.system_info()
        assert res["status"] in ("success", "error")

    def test_list_processes(self):
        provider = WindowsProvider()
        res = provider.list_processes(limit=5)
        assert res["status"] == "success"
        assert isinstance(res["data"]["processes"], list)
