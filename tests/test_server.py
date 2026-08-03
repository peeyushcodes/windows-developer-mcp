"""Unit and integration tests for server.py entry point."""

from fastmcp import FastMCP

from core.registry import ProviderRegistry
from server import _safe_register, create_app


class TestServerInitialization:
    """Test suite for server application creation and provider registration."""

    def test_create_app_returns_fastmcp_instance(self):
        app = create_app()
        assert isinstance(app, FastMCP)
        assert app.name == "Windows Developer MCP"

    def test_safe_register_success(self):
        registry = ProviderRegistry()
        _safe_register(registry, "python", "providers.python", "PythonProvider")
        assert "python" in registry.provider_names

    def test_safe_register_import_error_graceful_handling(self, caplog):
        registry = ProviderRegistry()
        # Should not raise an exception when importing non-existent module
        _safe_register(registry, "nonexistent", "providers.nonexistent_module", "NonExistentClass")
        assert "nonexistent" not in registry.provider_names
        assert "Could not import provider" in caplog.text

    def test_safe_register_instantiation_error_graceful_handling(self, caplog, monkeypatch):
        registry = ProviderRegistry()

        class FaultyProvider:
            def __init__(self):
                raise RuntimeError("Initialization boom")

        import types

        fake_module = types.ModuleType("providers.faulty")
        fake_module.FaultyProvider = FaultyProvider  # type: ignore[attr-defined]

        monkeypatch.setitem(__import__("sys").modules, "providers.faulty", fake_module)

        _safe_register(registry, "faulty", "providers.faulty", "FaultyProvider")
        assert "faulty" not in registry.provider_names
        assert "Failed to register provider" in caplog.text
