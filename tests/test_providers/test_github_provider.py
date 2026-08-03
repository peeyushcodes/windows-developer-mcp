"""
Unit tests for GitHubProvider.
"""

from providers.github import GitHubProvider


def test_github_provider_initialization():
    provider = GitHubProvider()
    assert provider.name == "github"


def test_github_auth_status():
    provider = GitHubProvider()
    res = provider.github_auth_status()
    assert res["status"] == "success"
    assert "token_present" in res["data"]
