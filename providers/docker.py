"""
Docker provider for Windows Developer MCP.

Provides Docker container, image, and Compose management.

Tools:
    docker_version        — Docker version
    docker_info           — Docker system info
    docker_list_images    — List images
    docker_list_containers — List containers
    docker_pull           — Pull an image
    docker_run            — Run a container
    docker_stop           — Stop a container
    docker_remove_container — Remove a container
    docker_logs           — Container logs
    docker_compose_up     — Start Compose services
    docker_compose_down   — Stop Compose services
    docker_compose_logs   — Compose service logs
    docker_build          — Build an image from Dockerfile
    docker_exec           — Execute command in container
"""

from __future__ import annotations

import logging
from typing import Any

from providers.base import BaseProvider, tool
from utils.json_utils import confirmation_required

logger = logging.getLogger(__name__)


class DockerProvider(BaseProvider):
    """
    Provides Docker container and image management tools.
    """

    name = "docker"
    description = "Docker images, containers, Compose services, logs, and builds."

    def _docker(self, args: str, tool_name: str, timeout: int = 60) -> dict[str, Any]:
        """Execute a docker command and return a shell response."""
        result = self._run_safe(f"docker {args}", tool_name=tool_name, timeout=timeout)
        return self._shell_response(result, tool_name=tool_name)

    @tool
    def docker_version(self) -> dict[str, Any]:
        """
        Return the installed Docker version.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_version()
        """
        return self._docker("version", tool_name="docker_version")

    @tool
    def docker_info(self) -> dict[str, Any]:
        """
        Return Docker system-wide information.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_info()
        """
        return self._docker("info", tool_name="docker_info")

    @tool
    def docker_list_images(self, all_images: bool = False) -> dict[str, Any]:
        """
        List Docker images.

        Args:
            all_images: If True, include intermediate image layers.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_list_images()
            docker_list_images(all_images=True)
        """
        flag = "--all" if all_images else ""
        return self._docker(f"images {flag}".strip(), tool_name="docker_list_images")

    @tool
    def docker_list_containers(self, all_containers: bool = False) -> dict[str, Any]:
        """
        List Docker containers.

        Args:
            all_containers: If True, include stopped containers.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_list_containers()
            docker_list_containers(all_containers=True)
        """
        flag = "--all" if all_containers else ""
        return self._docker(f"ps {flag}".strip(), tool_name="docker_list_containers")

    @tool
    def docker_pull(self, image: str, confirm: bool = False) -> dict[str, Any]:
        """
        Pull a Docker image from a registry.

        Args:
            image:   The image name and optional tag (e.g. "nginx:latest").
            confirm: Set to True to confirm when required by config.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_pull("nginx:latest", confirm=True)
            docker_pull("python:3.12-slim", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("docker_pull"):
            try:
                pm.assert_confirmed(action=f"docker pull {image}", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"docker pull {image}", tool="docker_pull")

        return self._docker(f"pull {image}", tool_name="docker_pull", timeout=300)

    @tool
    def docker_run(
        self,
        image: str,
        command: str = "",
        name: str = "",
        ports: str = "",
        detach: bool = True,
        remove: bool = False,
        env: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Run a Docker container.

        Args:
            image:   The image to run.
            command: Optional command to run inside the container.
            name:    Optional container name.
            ports:   Port mappings in Docker format (e.g. "8080:80").
            detach:  If True, run in detached mode (-d). Default: True.
            remove:  If True, remove container on exit (--rm).
            env:     Environment variable in KEY=VALUE format.
            confirm: Set to True to confirm when required by config.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_run("nginx:latest", ports="8080:80", confirm=True)
            docker_run("python:3.12", command="python -c 'print(1+1)'", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("docker_run"):
            try:
                pm.assert_confirmed(action=f"docker run {image}", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"docker run {image}", tool="docker_run")

        parts = ["run"]
        if detach:
            parts.append("-d")
        if remove:
            parts.append("--rm")
        if name:
            parts.extend(["--name", name])
        if ports:
            parts.extend(["-p", ports])
        if env:
            parts.extend(["-e", env])
        parts.append(image)
        if command:
            parts.append(command)

        return self._docker(" ".join(parts), tool_name="docker_run", timeout=120)

    @tool
    def docker_stop(self, container: str) -> dict[str, Any]:
        """
        Stop a running container.

        Args:
            container: The container name or ID.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_stop("my-nginx")
            docker_stop("abc123def456")
        """
        return self._docker(f"stop {container}", tool_name="docker_stop")

    @tool
    def docker_remove_container(
        self, container: str, force: bool = False, confirm: bool = False
    ) -> dict[str, Any]:
        """
        Remove a Docker container.

        Args:
            container: The container name or ID.
            force:     If True, force-remove a running container.
            confirm:   Set to True to confirm this destructive operation.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_remove_container("my-nginx", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("docker_remove_container"):
            try:
                pm.assert_confirmed(action=f"docker rm {container}", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"docker rm {container}", tool="docker_remove_container")

        force_flag = "--force" if force else ""
        return self._docker(f"rm {force_flag} {container}".strip(), tool_name="docker_remove_container")

    @tool
    def docker_logs(
        self, container: str, tail: int = 100, follow: bool = False
    ) -> dict[str, Any]:
        """
        Return logs from a container.

        Args:
            container: Container name or ID.
            tail:      Number of lines from the end to show. Default: 100.
            follow:    Stream logs (not recommended for MCP — use tail instead).

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_logs("my-nginx")
            docker_logs("my-app", tail=200)
        """
        follow_flag = "--follow" if follow else ""
        cmd = f"logs --tail={tail} {follow_flag} {container}".strip()
        return self._docker(cmd, tool_name="docker_logs", timeout=30)

    @tool
    def docker_exec(self, container: str, command: str) -> dict[str, Any]:
        """
        Execute a command inside a running container.

        Args:
            container: Container name or ID.
            command:   The command to run inside the container.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_exec("my-app", "ls /app")
            docker_exec("my-db", "psql -U postgres -c '\\\\l'")
        """
        return self._docker(f"exec {container} {command}", tool_name="docker_exec")

    @tool
    def docker_build(
        self,
        context: str = ".",
        tag: str = "",
        dockerfile: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Build a Docker image from a Dockerfile.

        Args:
            context:    Build context directory. Default: current directory.
            tag:        Image name and tag (e.g. "myapp:latest").
            dockerfile: Path to Dockerfile if not in the context root.
            confirm:    Set to True to confirm when required by config.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_build(tag="myapp:latest", confirm=True)
            docker_build(context=".", dockerfile="Dockerfile.prod", tag="myapp:prod", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("docker_build"):
            try:
                pm.assert_confirmed(action=f"docker build {context}", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required(f"docker build {context}", tool="docker_build")

        parts = ["build"]
        if tag:
            parts.extend(["-t", tag])
        if dockerfile:
            parts.extend(["-f", dockerfile])
        parts.append(context)
        return self._docker(" ".join(parts), tool_name="docker_build", timeout=600)

    @tool
    def docker_compose_up(
        self,
        file: str = "docker-compose.yml",
        services: str = "",
        detach: bool = True,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """
        Start Docker Compose services.

        Args:
            file:     Path to the Compose file. Default: "docker-compose.yml".
            services: Space-separated service names to start. Leave empty for all.
            detach:   Run in detached mode. Default: True.
            confirm:  Set to True to confirm when required by config.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_compose_up(confirm=True)
            docker_compose_up(services="web db", confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("docker_compose_up"):
            try:
                pm.assert_confirmed(action="docker compose up", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required("docker compose up", tool="docker_compose_up")

        detach_flag = "-d" if detach else ""
        cmd = f"compose -f {file} up {detach_flag} {services}".strip()
        return self._docker(cmd, tool_name="docker_compose_up", timeout=300)

    @tool
    def docker_compose_down(
        self, file: str = "docker-compose.yml", volumes: bool = False, confirm: bool = False
    ) -> dict[str, Any]:
        """
        Stop and remove Docker Compose services.

        Args:
            file:    Path to the Compose file.
            volumes: If True, also remove named volumes.
            confirm: Set to True to confirm.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_compose_down(confirm=True)
            docker_compose_down(volumes=True, confirm=True)
        """
        from core.exceptions import ConfirmationRequiredError
        from security.permissions import PermissionManager

        pm = PermissionManager()
        if pm.requires_confirmation("docker_compose_down"):
            try:
                pm.assert_confirmed(action="docker compose down", confirm=confirm)
            except ConfirmationRequiredError:
                return confirmation_required("docker compose down", tool="docker_compose_down")

        vol_flag = "--volumes" if volumes else ""
        cmd = f"compose -f {file} down {vol_flag}".strip()
        return self._docker(cmd, tool_name="docker_compose_down", timeout=120)

    @tool
    def docker_compose_logs(
        self, file: str = "docker-compose.yml", service: str = "", tail: int = 100
    ) -> dict[str, Any]:
        """
        Return logs from Docker Compose services.

        Args:
            file:    Path to the Compose file.
            service: Specific service name. Leave empty for all services.
            tail:    Number of lines to show per service. Default: 100.

        Returns:
            A dict with keys: status, exit_code, stdout, stderr, output, duration_ms.

        Examples:
            docker_compose_logs()
            docker_compose_logs(service="web", tail=50)
        """
        cmd = f"compose -f {file} logs --tail={tail} {service}".strip()
        return self._docker(cmd, tool_name="docker_compose_logs", timeout=30)
