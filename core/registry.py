"""
Provider registry and auto-registration engine for Windows Developer MCP.

The :class:`ProviderRegistry` collects :class:`BaseProvider` instances and
registers all their ``@tool``-decorated methods with a :class:`fastmcp.FastMCP`
application in a single call.

This eliminates the need to manually call ``mcp.tool(fn)`` for every new
tool. Adding a provider requires only two lines in ``server.py``:

.. code-block:: python

    registry.register(GitProvider())
    registry.register(PythonProvider())
    registry.register_all(mcp)

The registry also validates provider names are unique and that disabled
providers are excluded automatically.

Usage::

    from core.registry import ProviderRegistry

    registry = ProviderRegistry()
    registry.register(GitProvider())
    registry.register_all(mcp)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from providers.base import BaseProvider

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Collects providers and registers their tools with FastMCP.

    Lifecycle:
    1. Instantiate the registry.
    2. Call :meth:`register` for each provider.
    3. Call :meth:`register_all` once to bind all tools to FastMCP.

    The registry enforces:
    - Unique provider names (duplicate names raise ``ValueError``).
    - Disabled providers are skipped automatically.
    - At least one tool must be discovered per enabled provider.
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, provider: BaseProvider) -> None:
        """
        Add a provider to the registry.

        Args:
            provider: An instance of a :class:`BaseProvider` subclass.

        Raises:
            ValueError: If a provider with the same name is already registered.
            TypeError:  If ``provider`` is not a :class:`BaseProvider` instance.
        """
        if not isinstance(provider, BaseProvider):
            raise TypeError(
                f"Expected a BaseProvider instance, got {type(provider).__name__!r}."
            )
        if provider.name in self._providers:
            raise ValueError(
                f"Provider {provider.name!r} is already registered. "
                "Each provider must have a unique name."
            )
        self._providers[provider.name] = provider
        logger.debug("Registered provider: %r", provider.name)

    def register_all(self, mcp: FastMCP) -> dict[str, list[str]]:
        """
        Register all enabled provider tools with the FastMCP application.

        Iterates over all registered providers in insertion order. For each
        enabled provider, discovers ``@tool``-decorated methods and calls
        ``mcp.tool(method)`` for each one.

        Args:
            mcp: The :class:`fastmcp.FastMCP` application instance.

        Returns:
            A summary dict mapping provider names to lists of registered
            tool names, useful for startup logging.
        """
        summary: dict[str, list[str]] = {}

        for provider_name, provider in self._providers.items():
            if not provider.enabled:
                logger.info("Provider %r is disabled — skipping.", provider_name)
                continue

            tools = provider.get_tools()
            if not tools:
                logger.warning(
                    "Provider %r has no @tool methods — nothing registered.",
                    provider_name,
                )
                continue

            registered: list[str] = []
            for tool_fn in tools:
                try:
                    mcp.tool(tool_fn)
                    registered.append(tool_fn.__name__)
                    logger.debug("Registered tool: %s.%s", provider_name, tool_fn.__name__)
                except Exception as exc:
                    logger.error(
                        "Failed to register tool %s.%s: %s",
                        provider_name,
                        tool_fn.__name__,
                        exc,
                    )

            summary[provider_name] = registered
            logger.info(
                "Provider %r → %d tool(s): %s",
                provider_name,
                len(registered),
                ", ".join(registered),
            )

        total = sum(len(t) for t in summary.values())
        logger.info("Registry complete: %d provider(s), %d tool(s) total.", len(summary), total)
        return summary

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_provider(self, name: str) -> BaseProvider | None:
        """
        Return a registered provider by name, or ``None``.

        Args:
            name: The provider name (e.g. ``"git"``, ``"terminal"``).

        Returns:
            The :class:`BaseProvider` instance, or ``None`` if not found.
        """
        return self._providers.get(name)

    @property
    def provider_names(self) -> list[str]:
        """Return a list of all registered provider names (enabled or not)."""
        return list(self._providers.keys())

    @property
    def enabled_providers(self) -> list[BaseProvider]:
        """Return a list of all currently-enabled provider instances."""
        return [p for p in self._providers.values() if p.enabled]

    def summary(self) -> dict[str, Any]:
        """
        Return a JSON-serialisable registry summary for startup logging.

        Returns:
            A dict with counts and per-provider details.
        """
        providers = []
        for p in self._providers.values():
            tools = [fn.__name__ for fn in p.get_tools()] if p.enabled else []
            providers.append(
                {
                    "name": p.name,
                    "description": p.description,
                    "enabled": p.enabled,
                    "tool_count": len(tools),
                    "tools": tools,
                }
            )
        return {
            "total_providers": len(self._providers),
            "enabled_providers": sum(1 for p in self._providers.values() if p.enabled),
            "providers": providers,
        }

    def __len__(self) -> int:
        return len(self._providers)

    def __repr__(self) -> str:
        enabled = sum(1 for p in self._providers.values() if p.enabled)
        return (
            f"<ProviderRegistry "
            f"providers={len(self._providers)} "
            f"enabled={enabled}>"
        )
