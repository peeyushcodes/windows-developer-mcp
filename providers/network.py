"""
Network provider for Windows Developer MCP.

Provides network diagnostics and inspection tools.

Tools:
    ping              — Ping a host
    dns_lookup        — DNS name resolution
    get_ip_info       — Local IP addresses and interfaces
    get_open_ports    — List listening network ports
    http_get          — HTTP GET request (for testing APIs)
    traceroute        — Traceroute to a host
"""

from __future__ import annotations

import logging
from typing import Any

from providers.base import BaseProvider, tool
from utils.helpers import Timer
from utils.json_utils import error as make_error
from utils.json_utils import success

logger = logging.getLogger(__name__)


class NetworkProvider(BaseProvider):
    """
    Provides network diagnostics: ping, DNS, IP info, ports, and HTTP.
    """

    name = "network"
    description = "Ping, DNS lookup, IP info, open ports, and HTTP requests."

    @tool
    def ping(self, host: str, count: int = 4) -> dict[str, Any]:
        """
        Ping a host and return round-trip statistics.

        Args:
            host:  The hostname or IP address to ping.
            count: Number of ping packets to send (1–10). Default: 4.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            ping("google.com")
            ping("8.8.8.8", count=2)
        """
        count = max(1, min(count, 10))
        result = self._run_safe(f"ping -n {count} {host}", tool_name="ping")
        return self._shell_response(result, tool_name="ping")

    @tool
    def dns_lookup(self, hostname: str) -> dict[str, Any]:
        """
        Perform a DNS lookup for the given hostname.

        Args:
            hostname: The domain name to resolve (e.g. "github.com").

        Returns:
            A dict with keys: status, data (hostname, addresses list).

        Examples:
            dns_lookup("github.com")
            dns_lookup("google.com")
        """
        import socket

        with Timer() as t:
            try:
                addrs = socket.getaddrinfo(hostname, None)
                addresses = list({a[4][0] for a in addrs})
                return success(
                    {"hostname": hostname, "addresses": addresses, "count": len(addresses)},
                    tool="dns_lookup",
                    duration_ms=t.elapsed_ms,
                )
            except socket.gaierror as exc:
                return make_error(
                    f"DNS resolution failed for {hostname!r}: {exc}",
                    tool="dns_lookup",
                    code="DNS_ERROR",
                )

    @tool
    def get_ip_info(self) -> dict[str, Any]:
        """
        Return local network adapter information and IP addresses.

        Includes all IPv4 and IPv6 addresses for each active adapter.

        Returns:
            A dict with keys: status, data (hostname, adapters list).

        Examples:
            get_ip_info()
        """
        import socket

        import psutil

        with Timer() as t:
            try:
                hostname = socket.gethostname()
                adapters = []
                stats = psutil.net_if_stats()
                addresses = psutil.net_if_addrs()

                for name, addrs in sorted(addresses.items()):
                    stat = stats.get(name)
                    if stat and not stat.isup:
                        continue
                    addr_list = []
                    for addr in addrs:
                        if addr.family.name in ("AF_INET", "AF_INET6"):
                            addr_list.append(
                                {
                                    "family": addr.family.name,
                                    "address": addr.address,
                                    "netmask": addr.netmask,
                                }
                            )
                    if addr_list:
                        adapters.append({"name": name, "addresses": addr_list})

                return success(
                    {"hostname": hostname, "adapters": adapters},
                    tool="get_ip_info",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="get_ip_info", code="NETWORK_ERROR")

    @tool
    def get_open_ports(self, include_remote: bool = False) -> dict[str, Any]:
        """
        List locally open (listening) TCP and UDP ports.

        Args:
            include_remote: If True, also include established connections.

        Returns:
            A dict with keys: status, data (count, connections list).

        Examples:
            get_open_ports()
            get_open_ports(include_remote=True)
        """
        import psutil

        with Timer() as t:
            try:
                conns = psutil.net_connections(kind="all")
                results = []
                for conn in conns:
                    if not include_remote and conn.status not in ("LISTEN", ""):
                        continue
                    laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
                    results.append(
                        {
                            "protocol": conn.type.name if conn.type else "",
                            "local_address": laddr,
                            "status": conn.status,
                            "pid": conn.pid,
                        }
                    )
                results.sort(key=lambda c: c["local_address"])
                return success(
                    {"count": len(results), "connections": results},
                    tool="get_open_ports",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="get_open_ports", code="NETWORK_ERROR")

    @tool
    def http_get(
        self,
        url: str,
        timeout: int = 10,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Perform an HTTP GET request and return the response.

        Useful for testing APIs and web endpoints. Response body is
        truncated at 10,000 characters.

        Args:
            url:     The URL to request.
            timeout: Request timeout in seconds (1–60). Default: 10.
            headers: Optional request headers.

        Returns:
            A dict with keys: status, data (status_code, headers, body, url).

        Examples:
            http_get("https://api.github.com")
            http_get("https://httpbin.org/get", headers={"Accept": "application/json"})
        """
        import httpx

        timeout = max(1, min(timeout, 60))

        with Timer() as t:
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    response = client.get(url, headers=headers or {})

                body = response.text[:10_000]
                truncated = len(response.text) > 10_000

                return success(
                    {
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": body,
                        "truncated": truncated,
                        "content_type": response.headers.get("content-type", ""),
                    },
                    tool="http_get",
                    duration_ms=t.elapsed_ms,
                )
            except httpx.TimeoutException:
                return make_error(
                    f"Request timed out after {timeout}s",
                    tool="http_get",
                    code="TIMEOUT",
                )
            except Exception as exc:
                return make_error(str(exc), tool="http_get", code="REQUEST_ERROR")

    @tool
    def traceroute(self, host: str, max_hops: int = 15) -> dict[str, Any]:
        """
        Trace the network route to a host.

        Args:
            host:     The target hostname or IP address.
            max_hops: Maximum number of hops (1–30). Default: 15.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            traceroute("google.com")
            traceroute("8.8.8.8", max_hops=10)
        """
        max_hops = max(1, min(max_hops, 30))
        result = self._run_safe(
            f"tracert -h {max_hops} {host}", tool_name="traceroute"
        )
        return self._shell_response(result, tool_name="traceroute")
