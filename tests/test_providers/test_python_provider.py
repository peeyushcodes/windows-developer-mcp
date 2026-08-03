"""Unit tests for PythonProvider."""

from pathlib import Path

import pytest

from core.session import get_session, reset_session
from providers.python import PythonProvider


@pytest.fixture(autouse=True)
def setup_session():
    reset_session()
    session = get_session()
    session.change_directory(str(Path.cwd()))
    yield


class TestPythonProvider:
    def test_python_version(self):
        provider = PythonProvider()
        res = provider.python_version()
        assert res["status"] in ("success", "error")

    def test_pip_version(self):
        provider = PythonProvider()
        res = provider.pip_version()
        assert res["status"] in ("success", "error")

    def test_check_package(self):
        provider = PythonProvider()
        res = provider.check_package("fastmcp")
        assert res["status"] == "success"
        assert res["data"]["installed"] is True
