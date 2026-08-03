"""
Unit tests for SQLiteProvider.
"""

from providers.sqlite import SQLiteProvider


def test_sqlite_provider_initialization():
    provider = SQLiteProvider()
    assert provider.name == "sqlite"
