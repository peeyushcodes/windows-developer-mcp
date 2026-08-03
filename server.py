"""
Windows Developer MCP Server — Entry Point.

This module bootstraps the FastMCP application, initialises the security
and logging layer, registers all providers, and starts the server.

Architecture overview::

    server.py
      │
      ├── configure_logging()           ← sets up root logger from config
      ├── FastMCP("Windows Developer MCP")
      ├── ProviderRegistry()
      │     ├── register(TerminalProvider())
      │     ├── register(FilesystemProvider())
      │     ├── register(GitProvider())
      │     ├── register(PythonProvider())
      │     ├── register(NodeProvider())
      │     ├── register(DockerProvider())
      │     ├── register(WindowsProvider())
      │     ├── register(NetworkProvider())
      │     ├── register(SQLiteProvider())
      │     ├── register(ProjectProvider())
      │     ├── register(GitHubProvider())
      │     └── register(BrowserProvider())   ← stub, disabled by default
      └── registry.register_all(mcp)
            └── mcp.run()

Adding a new provider:
1. Create ``providers/<name>.py`` with a class inheriting :class:`BaseProvider`.
2. Decorate public methods with ``@tool``.
3. Add one ``registry.register(MyProvider())`` line below.
4. Enable it in ``config.toml`` under ``[providers]``.
"""

from __future__ import annotations

import json
import logging

from fastmcp import FastMCP

from core.config import load_config
from core.registry import ProviderRegistry
from security.logger import configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastMCP:
    """
    Construct and configure the FastMCP application.

    This function is the composition root of the application. It:
    1. Loads and validates configuration.
    2. Configures the application logger.
    3. Creates the FastMCP instance.
    4. Instantiates and registers all providers.
    5. Returns the configured app (without starting it).

    Returns:
        A fully configured :class:`fastmcp.FastMCP` instance ready to run.
    """
    # -----------------------------------------------------------------------
    # Bootstrap
    # -----------------------------------------------------------------------
    cfg = load_config()
    configure_logging()

    logger.info("=" * 60)
    logger.info("Windows Developer MCP v%s", cfg.server.version)
    logger.info("Workspace: %s", cfg.workspace.resolved_path)
    logger.info("Read-only: %s", cfg.workspace.read_only)
    logger.info("Profile:   %s", cfg.server.profile.value)
    logger.info("=" * 60)

    # -----------------------------------------------------------------------
    # FastMCP Application
    # -----------------------------------------------------------------------
    mcp = FastMCP(
        name=cfg.server.name,
        instructions=(
            "A production-grade Windows Developer MCP Server. "
            "Provides tools for terminal, git, python, node, docker, "
            "filesystem, network, Windows system, SQLite, project analysis, "
            "and GitHub — all with security validation and audit logging."
        ),
    )

    # -----------------------------------------------------------------------
    # Provider Registry
    # -----------------------------------------------------------------------
    registry = ProviderRegistry(profile=cfg.server.profile)

    # Import providers lazily to avoid circular imports and to give the
    # config/logging system time to initialise before providers load.
    # Each import is wrapped so a broken provider never crashes the server.

    _safe_register(registry, "terminal", "providers.terminal", "TerminalProvider")
    _safe_register(registry, "filesystem", "providers.filesystem", "FilesystemProvider")
    _safe_register(registry, "git", "providers.git", "GitProvider")
    _safe_register(registry, "python", "providers.python", "PythonProvider")
    _safe_register(registry, "node", "providers.node", "NodeProvider")
    _safe_register(registry, "docker", "providers.docker", "DockerProvider")
    _safe_register(registry, "windows", "providers.windows", "WindowsProvider")
    _safe_register(registry, "network", "providers.network", "NetworkProvider")
    _safe_register(registry, "sqlite", "providers.sqlite", "SQLiteProvider")
    _safe_register(registry, "project", "providers.project", "ProjectProvider")
    _safe_register(registry, "github", "providers.github", "GitHubProvider")
    _safe_register(registry, "browser", "providers.browser", "BrowserProvider")

    # Register all discovered tools with the FastMCP app.
    summary = registry.register_all(mcp)

    logger.info("Registered providers: %s", json.dumps(summary, indent=2))
    logger.info("Server ready. Starting MCP transport.")

    return mcp


def _safe_register(
    registry: ProviderRegistry,
    provider_name: str,
    module_path: str,
    class_name: str,
) -> None:
    """
    Import and register a provider, logging a warning if import fails.

    This prevents a single broken provider from taking down the entire server.

    Args:
        registry:      The :class:`ProviderRegistry` to register into.
        provider_name: The provider's ``name`` attribute (e.g. ``"git"``).
        module_path:   Dotted module path (e.g. ``"providers.git"``).
        class_name:    Class name within the module (e.g. ``"GitProvider"``).
    """
    try:
        import importlib

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        registry.register(cls())
        logger.debug("Loaded provider: %s (%s.%s)", provider_name, module_path, class_name)
    except ImportError as exc:
        logger.warning(
            "Could not import provider %r from %s: %s — skipping.",
            provider_name,
            module_path,
            exc,
        )
    except Exception as exc:
        logger.error(
            "Failed to register provider %r: %s — skipping.",
            provider_name,
            exc,
        )


# ==============================================================================
# Entry Point
# ==============================================================================

mcp = create_app()


def main() -> None:
    """CLI entry point registered in ``pyproject.toml`` as ``windows-developer-mcp``."""
    mcp.run()


if __name__ == "__main__":
    main()
