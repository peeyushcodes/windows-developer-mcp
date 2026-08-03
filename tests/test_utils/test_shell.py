"""Unit tests for utils/shell.py."""

import subprocess

from utils.shell import Shell, ShellResult, ShellRunner


class TestShellResult:
    def test_succeeded_property(self):
        res = ShellResult(stdout="ok", stderr="", exit_code=0, duration_ms=10, command="echo ok", shell=Shell.POWERSHELL)
        assert res.succeeded is True

        res_fail = ShellResult(stdout="", stderr="err", exit_code=1, duration_ms=10, command="echo err", shell=Shell.POWERSHELL)
        assert res_fail.succeeded is False

    def test_output_property(self):
        res = ShellResult(stdout="hello", stderr="", exit_code=0, duration_ms=10, command="echo hello", shell=Shell.POWERSHELL)
        assert res.output == "hello"

        res_err = ShellResult(stdout="", stderr="error out", exit_code=1, duration_ms=10, command="cmd", shell=Shell.CMD)
        assert res_err.output == "error out"

    def test_combined_property(self):
        res = ShellResult(stdout="out", stderr="err", exit_code=0, duration_ms=10, command="cmd", shell=Shell.POWERSHELL)
        assert res.combined == "out\nerr"

    def test_to_dict(self):
        res = ShellResult(stdout="out", stderr="", exit_code=0, duration_ms=15, command="test", shell=Shell.POWERSHELL)
        d = res.to_dict()
        assert d["stdout"] == "out"
        assert d["exit_code"] == 0
        assert d["succeeded"] is True


class TestShellRunner:
    def test_run_powershell_success(self):
        runner = ShellRunner()
        res = runner.run("Write-Host 'test_shell'", shell=Shell.POWERSHELL)
        assert res.succeeded is True
        assert "test_shell" in res.stdout

    def test_run_cmd_success(self):
        runner = ShellRunner()
        res = runner.run("echo test_cmd", shell=Shell.CMD)
        assert res.succeeded is True
        assert "test_cmd" in res.stdout

    def test_run_timeout_handling(self, monkeypatch):
        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="sleep", timeout=1)

        monkeypatch.setattr(subprocess, "run", mock_run)
        runner = ShellRunner()
        res = runner.run("sleep 100", timeout=1)
        assert res.succeeded is False
        assert res.exit_code == -1
        assert "timed out" in res.stderr

    def test_run_file_not_found_handling(self, monkeypatch):
        def mock_run(*args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", mock_run)
        runner = ShellRunner()
        res = runner.run("invalid_cmd", shell=Shell.POWERSHELL)
        assert res.succeeded is False
        assert res.exit_code == -1
        assert "not found" in res.stderr

    def test_truncate(self):
        runner = ShellRunner()
        text = "a" * 100
        truncated = runner._truncate(text, max_len=10)
        assert len(truncated) > 10
        assert "[Output truncated:" in truncated
