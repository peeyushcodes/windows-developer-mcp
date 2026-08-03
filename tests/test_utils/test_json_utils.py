"""Unit tests for utils/json_utils.py."""

from utils.json_utils import (
    confirmation_required,
    error,
    not_found,
    permission_denied,
    shell_result,
    success,
    validation_failed,
)


class TestJsonUtils:
    def test_success(self):
        res = success({"key": "val"}, tool="test_tool", duration_ms=50)
        assert res["status"] == "success"
        assert res["tool"] == "test_tool"
        assert res["data"]["key"] == "val"
        assert res["duration_ms"] == 50

    def test_error(self):
        res = error("Something failed", tool="test_tool", code="ERR_CODE", details={"line": 10})
        assert res["status"] == "error"
        assert res["tool"] == "test_tool"
        assert res["code"] == "ERR_CODE"
        assert res["message"] == "Something failed"
        assert res["details"]["line"] == 10

    def test_shell_result(self):
        res_ok = shell_result("stdout msg", "", 0, tool="cmd_tool", duration_ms=20, command="echo 1")
        assert res_ok["status"] == "success"
        assert res_ok["exit_code"] == 0
        assert res_ok["output"] == "stdout msg"

        res_fail = shell_result("", "stderr err", 1, tool="cmd_tool", duration_ms=20, command="exit 1")
        assert res_fail["status"] == "error"
        assert res_fail["exit_code"] == 1
        assert res_fail["output"] == "stderr err"

    def test_specialized_errors(self):
        nf = not_found("file test.py", tool="t")
        assert nf["code"] == "NOT_FOUND"

        pd = permission_denied("no write", tool="t")
        assert pd["code"] == "PERMISSION_DENIED"

        vf = validation_failed("invalid input", tool="t")
        assert vf["code"] == "VALIDATION_ERROR"

        cr = confirmation_required("delete file", tool="t")
        assert cr["code"] == "CONFIRMATION_REQUIRED"
