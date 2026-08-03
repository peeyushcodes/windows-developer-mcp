import sys

sys.path.insert(0, '.')

from pathlib import Path

from core.session import get_session, reset_session
from providers.browser import BrowserProvider
from providers.filesystem import FilesystemProvider
from providers.git import GitProvider
from providers.python import PythonProvider
from providers.terminal import TerminalProvider

# Reset session to workspace root for testing
reset_session()
session = get_session()
session.change_directory(str(Path.cwd()))
print("Session cwd set to:", session.cwd)

print()
print("=== Functional Tests ===")

# Terminal tests
tp = TerminalProvider()
result = tp.run_powershell("Write-Host hello")
print("terminal.run_powershell:", result["status"], "-", result.get("output", ""))

result = tp.get_working_directory()
print("terminal.get_working_directory:", result["data"]["cwd"])

result = tp.get_session_info()
print("terminal.get_session_info: started_at=" + str(result["data"]["started_at"]))

# Git tests
gp = GitProvider()
result = gp.git_status()
print("git.git_status:", result["status"], "exit:", result["exit_code"])

result = gp.git_log(limit=3)
print("git.git_log:", result["status"])

result = gp.git_branch()
print("git.git_branch:", result["status"])

# Python tests
pp = PythonProvider()
result = pp.python_version()
print("python.python_version:", result.get("output", result.get("stdout", "")))

result = pp.pip_version()
print("python.pip_version:", result.get("output", "")[:40])

result = pp.check_package("fastmcp")
print("python.check_package fastmcp: installed=" + str(result["data"]["installed"]))

# Filesystem tests
fp = FilesystemProvider()
result = fp.list_directory(".")
print("filesystem.list_directory:", result["status"], "count:", result.get("data", {}).get("count", "N/A"))

result = fp.file_exists("server.py")
print("filesystem.file_exists server.py:", result["data"]["exists"])

result = fp.read_file("config.toml")
print("filesystem.read_file config.toml:", result["status"], "lines:", result.get("data", {}).get("lines", "N/A"))

result = fp.tree(".", max_depth=2)
print("filesystem.tree:", result["status"], "files:", result.get("data", {}).get("file_count", "N/A"))

result = fp.search_files(".", pattern="*.py")
print("filesystem.search_files *.py:", result["status"], "found:", result.get("data", {}).get("count", "N/A"))

# Browser tests
bp = BrowserProvider()
result = bp.check_url("https://httpbin.org/get")
print("browser.check_url httpbin.org:", result["status"], "status_code:", result.get("data", {}).get("status_code", "N/A"))

result = bp.extract_text("https://httpbin.org/html")
print("browser.extract_text httpbin.org:", result["status"], "title:", result.get("data", {}).get("title", "N/A"))

# Security tests
print()
print("=== Security Tests ===")
result = tp.run_powershell("shutdown /s /t 0")
print("blocked shutdown:", result["status"], "-", result.get("output", "")[:80])

result = tp.run_powershell("format c:")
print("blocked format:", result["status"], "-", result.get("output", "")[:80])

result = tp.run_powershell("net user admin /add")
print("blocked net user:", result["status"], "-", result.get("output", "")[:80])

print()
print("=== All tests complete ===")
