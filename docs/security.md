# Security Model & Policy — Windows Developer MCP Server

Security is a foundational pillar of **Windows Developer MCP**. The server executes commands on Windows developer machines on behalf of AI models. Therefore, strict multi-layered security guards are enforced at every boundary.

---

## Security Layer Overview

```
[ LLM Request ] ──> [ Workspace Sandbox ] ──> [ Command Validator ] ──> [ Rate Limiter ] ──> [ Audit Logger ] ──> [ Windows Subprocess ]
```

---

## 1. Workspace Sandbox Boundary (`security/sandbox.py`)
- All file operations and shell commands are strictly locked to the configured workspace root directory (`cfg.workspace.resolved_path`).
- Paths are resolved and normalized using `Path.resolve()` to eliminate path traversal exploits (`../..`).
- Any attempt to access files outside the workspace raises a `WorkspaceViolationError` and aborts execution.

## 2. Command Validation Engine (`security/validator.py`)
- Commands are evaluated against built-in regex denylists (`security/dangerous_commands.py`).
- Blocked operations include:
  - System shutdown / restart (`shutdown /s`)
  - Volume formatting (`format c:`)
  - Mass deletion (`del /f /s /q C:\*`)
  - User privilege escalation (`net user admin /add`)
  - Execution policy bypass (`Set-ExecutionPolicy Bypass`)
  - Encoded PowerShell commands (`powershell -enc`)

## 3. Destructive Command Confirmation Policy (`security/permissions.py`)
- Operations marked as destructive (file deletion, table drops, pruning containers) require explicit user parameter confirmation (`confirm = true`).

## 4. Execution Timeout & Rate Limiting (`security/rate_limiter.py`)
- Subprocesses strictly enforce a configurable timeout (`cfg.security.timeout`, default 60s).
- Subprocesses exceeding the timeout are forcibly terminated via process group signals.
- A sliding-window rate limiter prevents automated loop flooding.

## 5. Audit Logging (`security/logger.py`)
- Every executed tool call, command string, execution duration, and exit status is logged to structured JSON files in `logs/audit.log`.
