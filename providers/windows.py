"""
Windows system provider for Windows Developer MCP.

Exposes Windows-specific system information via psutil and the Windows API:
CPU, memory, disk, processes, services, and environment.

Tools:
    system_info       — OS, hardware, and Python info
    cpu_info          — CPU usage and core details
    memory_info       — RAM and virtual memory stats
    disk_info         — Disk partitions and usage
    list_processes    — Running process list
    get_process       — Info about a specific process
    list_services     — Windows services
    windows_version   — Windows version details
"""

from __future__ import annotations

from datetime import UTC
import logging
import platform
from typing import Any

from providers.base import BaseProvider, tool
from utils.helpers import Timer, format_size
from utils.json_utils import error as make_error
from utils.json_utils import success

logger = logging.getLogger(__name__)


class WindowsProvider(BaseProvider):
    """
    Provides Windows system information via psutil.

    All operations are read-only — this provider never modifies system state.
    """

    name = "windows"
    description = "CPU, memory, disk, processes, services, and Windows system information."

    @tool
    def system_info(self) -> dict[str, Any]:
        """
        Return comprehensive system information.

        Includes OS version, hostname, uptime, Python version, architecture,
        and processor brand.

        Returns:
            A dict with keys: status, data (detailed system snapshot).

        Examples:
            system_info()
        """
        from datetime import datetime
        import getpass

        import psutil

        with Timer() as t:
            try:
                boot_ts = psutil.boot_time()
                uptime_secs = int(
                    (datetime.now(UTC) - datetime.fromtimestamp(boot_ts, tz=UTC))
                    .total_seconds()
                )
                hours, remainder = divmod(uptime_secs, 3600)
                minutes, seconds = divmod(remainder, 60)

                return success(
                    {
                        "hostname": platform.node(),
                        "username": getpass.getuser(),
                        "os": platform.system(),
                        "os_version": platform.version(),
                        "os_release": platform.release(),
                        "architecture": platform.machine(),
                        "processor": platform.processor(),
                        "python_version": platform.python_version(),
                        "uptime": f"{hours}h {minutes}m {seconds}s",
                        "uptime_seconds": uptime_secs,
                        "boot_time": datetime.fromtimestamp(
                            boot_ts, tz=UTC
                        ).isoformat(),
                    },
                    tool="system_info",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="system_info", code="SYSTEM_ERROR")

    @tool
    def windows_version(self) -> dict[str, Any]:
        """
        Return detailed Windows version information.

        Returns:
            A dict with keys: status, data (version, build, edition strings).

        Examples:
            windows_version()
        """
        with Timer() as t:
            result = self._run_safe(
                "Get-ComputerInfo | Select-Object WindowsVersion, OsName, OsBuildNumber, "
                "OsArchitecture | ConvertTo-Json",
                tool_name="windows_version",
            )
            if result.succeeded:
                import json
                try:
                    data = json.loads(result.stdout)
                    return success(data, tool="windows_version", duration_ms=t.elapsed_ms)
                except Exception:
                    pass
            return success(
                {
                    "version": platform.version(),
                    "release": platform.release(),
                    "machine": platform.machine(),
                },
                tool="windows_version",
                duration_ms=t.elapsed_ms,
            )

    @tool
    def cpu_info(self) -> dict[str, Any]:
        """
        Return CPU usage statistics and core information.

        Returns:
            A dict with keys: status, data (cores, usage%, frequency).

        Examples:
            cpu_info()
        """
        import psutil

        with Timer() as t:
            try:
                freq = psutil.cpu_freq()
                return success(
                    {
                        "physical_cores": psutil.cpu_count(logical=False),
                        "logical_cores": psutil.cpu_count(logical=True),
                        "usage_percent": psutil.cpu_percent(interval=0.1),
                        "per_core_percent": psutil.cpu_percent(interval=0.1, percpu=True),
                        "frequency_mhz": {
                            "current": round(freq.current, 1) if freq else None,
                            "min": round(freq.min, 1) if freq else None,
                            "max": round(freq.max, 1) if freq else None,
                        },
                        "processor": platform.processor(),
                    },
                    tool="cpu_info",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="cpu_info", code="SYSTEM_ERROR")

    @tool
    def memory_info(self) -> dict[str, Any]:
        """
        Return RAM and virtual memory statistics.

        Returns:
            A dict with keys: status, data (total, available, used, percent for RAM and swap).

        Examples:
            memory_info()
        """
        import psutil

        with Timer() as t:
            try:
                ram = psutil.virtual_memory()
                swap = psutil.swap_memory()
                return success(
                    {
                        "ram": {
                            "total": format_size(ram.total),
                            "total_bytes": ram.total,
                            "available": format_size(ram.available),
                            "used": format_size(ram.used),
                            "percent": ram.percent,
                        },
                        "swap": {
                            "total": format_size(swap.total),
                            "used": format_size(swap.used),
                            "free": format_size(swap.free),
                            "percent": swap.percent,
                        },
                    },
                    tool="memory_info",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="memory_info", code="SYSTEM_ERROR")

    @tool
    def disk_info(self) -> dict[str, Any]:
        """
        Return disk partition information and usage for each drive.

        Returns:
            A dict with keys: status, data (list of partition details).

        Examples:
            disk_info()
        """
        import psutil

        with Timer() as t:
            try:
                partitions = []
                for part in psutil.disk_partitions(all=False):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        partitions.append(
                            {
                                "device": part.device,
                                "mountpoint": part.mountpoint,
                                "filesystem": part.fstype,
                                "total": format_size(usage.total),
                                "used": format_size(usage.used),
                                "free": format_size(usage.free),
                                "percent": usage.percent,
                                "total_bytes": usage.total,
                            }
                        )
                    except (PermissionError, OSError):
                        partitions.append(
                            {
                                "device": part.device,
                                "mountpoint": part.mountpoint,
                                "filesystem": part.fstype,
                                "error": "Access denied",
                            }
                        )
                return success(
                    {"count": len(partitions), "partitions": partitions},
                    tool="disk_info",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="disk_info", code="SYSTEM_ERROR")

    @tool
    def list_processes(
        self,
        sort_by: str = "memory",
        limit: int = 25,
        filter_name: str = "",
    ) -> dict[str, Any]:
        """
        List running processes with resource usage.

        Args:
            sort_by:     Sort field — "memory", "cpu", "pid", or "name".
                         Default: "memory".
            limit:       Maximum number of processes to return (1–200).
            filter_name: Optional substring filter on process name.

        Returns:
            A dict with keys: status, data (count, processes list).

        Examples:
            list_processes()
            list_processes(sort_by="cpu", limit=10)
            list_processes(filter_name="python")
        """
        import psutil

        limit = max(1, min(limit, 200))
        valid_sorts = {"memory", "cpu", "pid", "name"}
        if sort_by not in valid_sorts:
            sort_by = "memory"

        with Timer() as t:
            try:
                procs = []
                for proc in psutil.process_iter(
                    ["pid", "name", "username", "memory_percent", "cpu_percent", "status"]
                ):
                    try:
                        info = proc.info  # type: ignore[attr-defined]
                        if filter_name and filter_name.lower() not in (info["name"] or "").lower():
                            continue
                        procs.append(
                            {
                                "pid": info["pid"],
                                "name": info["name"],
                                "username": info.get("username", ""),
                                "memory_percent": round(info["memory_percent"] or 0.0, 2),
                                "cpu_percent": round(info["cpu_percent"] or 0.0, 2),
                                "status": info["status"],
                            }
                        )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                sort_key = {
                    "memory": lambda p: p["memory_percent"],
                    "cpu": lambda p: p["cpu_percent"],
                    "pid": lambda p: p["pid"],
                    "name": lambda p: (p["name"] or "").lower(),
                }[sort_by]

                procs.sort(key=sort_key, reverse=(sort_by in {"memory", "cpu"}))
                procs = procs[:limit]

                return success(
                    {"count": len(procs), "sort_by": sort_by, "processes": procs},
                    tool="list_processes",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="list_processes", code="SYSTEM_ERROR")

    @tool
    def get_process(self, pid: int) -> dict[str, Any]:
        """
        Return detailed information about a specific process.

        Args:
            pid: The process ID (PID) to inspect.

        Returns:
            A dict with keys: status, data (process details including memory, cpu, files).

        Examples:
            get_process(1234)
        """
        import psutil

        from utils.json_utils import not_found

        with Timer() as t:
            try:
                proc = psutil.Process(pid)
                with proc.oneshot():
                    info = {
                        "pid": proc.pid,
                        "name": proc.name(),
                        "exe": proc.exe() if proc.is_running() else "",
                        "status": proc.status(),
                        "username": proc.username() if hasattr(proc, "username") else "",
                        "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 2),
                        "cpu_percent": proc.cpu_percent(interval=0.1),
                        "threads": proc.num_threads(),
                        "created": proc.create_time(),
                    }
                return success(info, tool="get_process", duration_ms=t.elapsed_ms)
            except psutil.NoSuchProcess:
                return not_found(f"Process with PID {pid}", tool="get_process")
            except psutil.AccessDenied:
                return make_error(
                    f"Access denied to process {pid}.",
                    tool="get_process",
                    code="ACCESS_DENIED",
                )
            except Exception as exc:
                return make_error(str(exc), tool="get_process", code="SYSTEM_ERROR")

    @tool
    def list_services(self, filter_name: str = "", status_filter: str = "") -> dict[str, Any]:
        """
        List Windows services with their status.

        Args:
            filter_name:   Optional substring filter on service name.
            status_filter: Filter by status — "running", "stopped", or "" for all.

        Returns:
            A dict with keys: status, data (count, services list).

        Examples:
            list_services()
            list_services(status_filter="running")
            list_services(filter_name="sql")
        """
        with Timer() as t:
            cmd = "Get-Service | Select-Object Name, DisplayName, Status | ConvertTo-Json"
            result = self._run_safe(cmd, tool_name="list_services")
            if not result.succeeded:
                return make_error(result.stderr, tool="list_services", code="EXECUTION_ERROR")

            import json
            try:
                raw = json.loads(result.stdout)
                if isinstance(raw, dict):
                    raw = [raw]
                services = []
                for svc in raw:
                    name = svc.get("Name", "")
                    display = svc.get("DisplayName", "")
                    status_val = str(svc.get("Status", {}).get("Value__", ""))
                    status_str = "Running" if status_val == "4" else "Stopped"
                    if filter_name and filter_name.lower() not in name.lower():
                        continue
                    if status_filter and status_str.lower() != status_filter.lower():
                        continue
                    services.append(
                        {"name": name, "display_name": display, "status": status_str}
                    )
                return success(
                    {"count": len(services), "services": services},
                    tool="list_services",
                    duration_ms=t.elapsed_ms,
                )
            except Exception as exc:
                return make_error(str(exc), tool="list_services", code="PARSE_ERROR")
