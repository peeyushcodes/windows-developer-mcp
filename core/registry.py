"""
Provider registry and auto-registration engine for Windows Developer MCP.

The :class:`ProviderRegistry` collects :class:`BaseProvider` instances and
registers their ``@tool``-decorated methods with a :class:`fastmcp.FastMCP`
application, supporting profile-based filtering, lazy loading, and meta-tools.

Profiles:
- ``MINIMAL``:   Exposes core essential tools (~8-12 tools) to conserve LLM context.
- ``DEVELOPER``: Exposes primary developer tools (~25 tools).
- ``FULL``:      Exposes all available tools across all active providers (Glama mode).
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

from core.config import ServerProfile, get_config
from providers.base import BaseProvider

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Tools included in MINIMAL profile to optimize context footprint for local LLMs.
_MINIMAL_TOOL_ALLOWLIST = {
    "terminal_run",
    "filesystem_read",
    "filesystem_write",
    "git_status",
    "project_analyze",
    "windows_system_info",
    "python_run",
    "node_run",
    "mcp_search_tools",
    "mcp_list_profiles",
    "mcp_enable_provider",
}

# Tools excluded in DEVELOPER profile (leaving advanced/niche tools for FULL profile).
_DEVELOPER_TOOL_EXCLUSIONS = {
    "network_ping",
    "windows_env_var_get",
    "sqlite_schema",
    "git_stash_pop",
}


class ProviderRegistry:
    """
    Collects providers and registers their tools with FastMCP based on execution profile.

    Lifecycle:
    1. Instantiate the registry.
    2. Call :meth:`register` or :meth:`lazy_load` for providers.
    3. Call :meth:`register_all` once to bind filtered tools and meta-tools to FastMCP.
    """

    def __init__(self, profile: ServerProfile | None = None) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._profile: ServerProfile = profile or get_config().server.profile

    @property
    def profile(self) -> ServerProfile:
        """Return the active server execution profile."""
        return self._profile

    @profile.setter
    def profile(self, val: ServerProfile) -> None:
        """Update active server execution profile."""
        self._profile = val

    # ------------------------------------------------------------------
    # Registration & Lifecycle
    # ------------------------------------------------------------------

    def register(self, provider: BaseProvider) -> None:
        """
        Add a provider instance to the registry.

        Args:
            provider: An instance of a :class:`BaseProvider` subclass.
        """
        if not isinstance(provider, BaseProvider):
            raise TypeError(f"Expected a BaseProvider instance, got {type(provider).__name__!r}.")
        if provider.name in self._providers:
            raise ValueError(
                f"Provider {provider.name!r} is already registered. "
                "Each provider must have a unique name."
            )
        self._providers[provider.name] = provider
        logger.debug("Registered provider: %r", provider.name)

    def unregister(self, provider_name: str) -> BaseProvider | None:
        """
        Remove and return a provider from the registry by name.

        Args:
            provider_name: Snake_case name of the provider to remove.

        Returns:
            The removed provider instance, or None if not found.
        """
        removed = self._providers.pop(provider_name, None)
        if removed:
            logger.info("Unregistered provider: %r", provider_name)
        return removed

    def lazy_load(
        self, provider_name: str, module_path: str, class_name: str
    ) -> BaseProvider | None:
        """
        Import and register a provider dynamically on demand.

        Args:
            provider_name: Unique provider identifier (e.g. ``"docker"``).
            module_path: Dotted Python module path (e.g. ``"providers.docker"``).
            class_name: Provider class name (e.g. ``"DockerProvider"``).

        Returns:
            The instantiated :class:`BaseProvider` instance, or None if import failed.
        """
        if provider_name in self._providers:
            return self._providers[provider_name]

        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            instance: BaseProvider = cls()
            self.register(instance)
            logger.info("Lazy-loaded provider %r (%s.%s)", provider_name, module_path, class_name)
            return instance
        except Exception as exc:
            logger.error("Lazy loading failed for provider %r: %s", provider_name, exc)
            return None

    # ------------------------------------------------------------------
    # Tool Binding & Profile Filtering
    # ------------------------------------------------------------------

    def should_expose_tool(self, tool_name: str) -> bool:
        """
        Determine whether a tool should be exposed under the active profile.

        Args:
            tool_name: The function name of the tool.

        Returns:
            True if the tool is active under current profile, False otherwise.
        """
        if self._profile == ServerProfile.FULL:
            return True
        if self._profile == ServerProfile.MINIMAL:
            return tool_name in _MINIMAL_TOOL_ALLOWLIST
        if self._profile == ServerProfile.DEVELOPER:
            return tool_name not in _DEVELOPER_TOOL_EXCLUSIONS
        return True

    def register_all(self, mcp: FastMCP) -> dict[str, list[str]]:
        """
        Register enabled provider tools and meta-tools with FastMCP.

        Args:
            mcp: The :class:`fastmcp.FastMCP` application instance.

        Returns:
            A summary dict mapping provider names to lists of registered tools.
        """
        summary: dict[str, list[str]] = {}

        # 1. Register Provider Tools
        for provider_name, provider in self._providers.items():
            if not provider.enabled:
                logger.info("Provider %r is disabled — skipping.", provider_name)
                continue

            tools = provider.get_tools()
            if not tools:
                continue

            registered: list[str] = []
            for tool_fn in tools:
                tool_name = tool_fn.__name__
                if not self.should_expose_tool(tool_name):
                    logger.debug(
                        "Skipping tool %s under profile %s", tool_name, self._profile.value
                    )
                    continue

                try:
                    mcp.tool(tool_fn)
                    registered.append(tool_name)
                    logger.debug("Registered tool: %s.%s", provider_name, tool_name)
                except Exception as exc:
                    logger.error("Failed to register tool %s.%s: %s", provider_name, tool_name, exc)

            summary[provider_name] = registered

        # 2. Register Dynamic Meta-Tools
        self._register_meta_tools(mcp)

        total = sum(len(t) for t in summary.values())
        logger.info(
            "Registry complete [Profile: %s]: %d provider(s), %d tool(s) registered.",
            self._profile.value,
            len(summary),
            total,
        )
        return summary

    def _register_meta_tools(self, mcp: FastMCP) -> None:
        """Register dynamic capability discovery meta-tools."""
        registry_self = self

        @mcp.tool
        def mcp_search_tools(query: str = "") -> dict[str, Any]:
            """
            Search available tools and capabilities across all registered providers.

            Use this tool to discover extra capabilities when operating under minimal context profile.

            Args:
                query: Search filter (matches tool name or description).

            Returns:
                Matching tools organized by provider.
            """
            results: dict[str, list[dict[str, str]]] = {}
            query_lower = query.lower()

            for p_name, provider in registry_self._providers.items():
                if not provider.enabled:
                    continue
                p_tools = []
                for fn in provider.get_tools():
                    doc = fn.__doc__ or ""
                    if (
                        not query
                        or query_lower in fn.__name__.lower()
                        or query_lower in doc.lower()
                    ):
                        p_tools.append(
                            {
                                "name": fn.__name__,
                                "description": doc.strip().split("\n")[0],
                                "exposed": registry_self.should_expose_tool(fn.__name__),
                            }
                        )
                if p_tools:
                    results[p_name] = p_tools

            return {
                "active_profile": registry_self._profile.value,
                "query": query,
                "total_matches": sum(len(v) for v in results.values()),
                "providers": results,
            }

        @mcp.tool
        def mcp_list_profiles() -> dict[str, Any]:
            """
            List available server execution profiles and current status.

            Returns:
                Current profile and profile descriptions.
            """
            return {
                "current_profile": registry_self._profile.value,
                "available_profiles": [p.value for p in ServerProfile],
                "descriptions": {
                    "minimal": "Lightweight context footprint (<10 core tools), optimal for 7B/8B local models.",
                    "developer": "Balanced toolset (~25 core developer tools) for standard tasks.",
                    "full": "Complete API tool exposure across all active providers.",
                },
            }

        @mcp.tool
        def mcp_enable_provider(provider_name: str) -> dict[str, Any]:
            """
            Dynamically ensure a provider is loaded and return its capability summary.

            Args:
                provider_name: Provider name to activate (e.g. 'docker', 'sqlite', 'github').

            Returns:
                Activation status and available provider tools.
            """
            provider = registry_self.get_provider(provider_name)
            if not provider:
                # Attempt lazy load
                provider = registry_self.lazy_load(
                    provider_name,
                    f"providers.{provider_name}",
                    f"{provider_name.capitalize()}Provider",
                )

            if not provider:
                return {
                    "status": "error",
                    "message": f"Provider '{provider_name}' could not be loaded.",
                }

            tools = [fn.__name__ for fn in provider.get_tools()]
            return {
                "status": "success",
                "provider": provider_name,
                "enabled": provider.enabled,
                "tool_count": len(tools),
                "tools": tools,
            }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_provider(self, name: str) -> BaseProvider | None:
        """Return a registered provider by name, or None."""
        return self._providers.get(name)

    @property
    def provider_names(self) -> list[str]:
        """Return a list of all registered provider names."""
        return list(self._providers.keys())

    @property
    def enabled_providers(self) -> list[BaseProvider]:
        """Return a list of all currently-enabled provider instances."""
        return [p for p in self._providers.values() if p.enabled]

    def summary(self) -> dict[str, Any]:
        """Return a JSON-serializable registry summary."""
        providers = []
        for p in self._providers.values():
            tools = (
                [fn.__name__ for fn in p.get_tools() if self.should_expose_tool(fn.__name__)]
                if p.enabled
                else []
            )
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
            "profile": self._profile.value,
            "total_providers": len(self._providers),
            "enabled_providers": sum(1 for p in self._providers.values() if p.enabled),
            "providers": providers,
        }

    def __len__(self) -> int:
        return len(self._providers)

    def __repr__(self) -> str:
        return (
            f"<ProviderRegistry profile={self._profile.value!r} providers={len(self._providers)}>"
        )
