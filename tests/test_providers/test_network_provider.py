"""Unit tests for NetworkProvider."""

from pathlib import Path

import pytest

from core.session import get_session, reset_session
from providers.network import NetworkProvider


@pytest.fixture(autouse=True)
def setup_session():
    reset_session()
    session = get_session()
    session.change_directory(str(Path.cwd()))
    yield


class TestNetworkProvider:
    def test_dns_lookup(self):
        provider = NetworkProvider()
        res = provider.dns_lookup("localhost")
        assert res["status"] in ("success", "error")
