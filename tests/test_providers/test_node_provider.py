"""Unit tests for NodeProvider."""

from pathlib import Path

import pytest

from core.session import get_session, reset_session
from providers.node import NodeProvider


@pytest.fixture(autouse=True)
def setup_session():
    reset_session()
    session = get_session()
    session.change_directory(str(Path.cwd()))
    yield


class TestNodeProvider:
    def test_node_version(self):
        provider = NodeProvider()
        res = provider.node_version()
        assert res["status"] in ("success", "error")

    def test_npm_version(self):
        provider = NodeProvider()
        res = provider.npm_version()
        assert res["status"] in ("success", "error")
