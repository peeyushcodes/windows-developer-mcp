"""
Unit tests for ProviderRegistry profiles, unregistering, lazy loading, and meta-tools.
"""

from fastmcp import FastMCP

from core.config import ServerProfile
from core.registry import ProviderRegistry
from providers.git import GitProvider
from providers.terminal import TerminalProvider


def test_registry_initialization_with_profile():
    registry = ProviderRegistry(profile=ServerProfile.MINIMAL)
    assert registry.profile == ServerProfile.MINIMAL


def test_should_expose_tool_minimal_profile():
    registry = ProviderRegistry(profile=ServerProfile.MINIMAL)
    assert registry.should_expose_tool("terminal_run") is True
    assert registry.should_expose_tool("project_analyze") is True
    assert registry.should_expose_tool("network_ping") is False


def test_should_expose_tool_full_profile():
    registry = ProviderRegistry(profile=ServerProfile.FULL)
    assert registry.should_expose_tool("terminal_run") is True
    assert registry.should_expose_tool("network_ping") is True


def test_unregister_provider():
    registry = ProviderRegistry()
    git_provider = GitProvider()
    registry.register(git_provider)
    assert "git" in registry.provider_names

    removed = registry.unregister("git")
    assert removed is git_provider
    assert "git" not in registry.provider_names


def test_lazy_load_provider():
    registry = ProviderRegistry()
    provider = registry.lazy_load("git", "providers.git", "GitProvider")
    assert provider is not None
    assert provider.name == "git"
    assert "git" in registry.provider_names


def test_meta_tools_registration():
    mcp = FastMCP("TestApp")
    registry = ProviderRegistry(profile=ServerProfile.MINIMAL)
    registry.register(TerminalProvider())
    summary = registry.register_all(mcp)
    assert "terminal" in summary
