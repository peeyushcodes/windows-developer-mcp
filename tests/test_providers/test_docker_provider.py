"""
Unit tests for DockerProvider.
"""

from unittest.mock import patch

from providers.docker import DockerProvider
from utils.shell import Shell, ShellResult


def test_docker_provider_initialization():
    provider = DockerProvider()
    assert provider.name == "docker"


@patch.object(DockerProvider, "_run_safe")
def test_docker_list_containers(mock_run_safe):
    mock_run_safe.return_value = ShellResult(
        stdout="CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES\n",
        stderr="",
        exit_code=0,
        duration_ms=10,
        command="docker ps",
        shell=Shell.POWERSHELL,
    )
    provider = DockerProvider()
    res = provider.docker_list_containers()
    assert res["status"] == "success"
    assert "CONTAINER ID" in res["stdout"]
