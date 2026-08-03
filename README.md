# Windows Developer MCP Server

A production-grade **Model Context Protocol (MCP)** server for Windows developer environments. Built on [FastMCP](https://github.com/jlowin/fastmcp), it equips AI assistants (e.g. LM Studio, Claude Desktop, VS Code extension) with comprehensive capabilities for terminal execution, filesystem navigation, git operations, runtime inspections, container management, SQLite queries, web browser interaction, and security-sandboxed system control.

---

## Key Features

- 🖥️ **Windows Terminal Provider**: PowerShell & CMD execution with execution limits, custom working directory support, and background session tracking.
- 📁 **Filesystem Provider**: Safe file reading, structured writing, directory trees, file searches, hash generation, and metadata inspection.
- 🌿 **Git Provider**: Repository status, commit logs, branch management, diffs, and staging support.
- 🐍 **Python Provider**: Virtual environment management, package inspection, module verification, and version details.
- 🟢 **Node.js Provider**: Node & npm version detection, global/local package details, and script runner inspection.
- 🐳 **Docker Provider**: Container listing, inspection, log tailing, image management, and compose state checks.
- ⚙️ **Windows System Provider**: Hardware/OS info, process manager, environment variable inspector, and system metrics.
- 🌐 **Network Provider**: DNS resolution, ping utilities, port connectivity checks, and HTTP/HTTPS header inspections.
- 🗄️ **SQLite Provider**: Database schema inspection, safe parameterized queries, table listing, and index overview.
- 📊 **Project Provider**: Automated project type detection (Python, Node, Rust, Go, C#), dependency tree analysis, and structure summary.
- 🐙 **GitHub Provider**: Public/private repository inspection, issue tracking, PR status, release fetching, and search via GitHub API / `gh` CLI.
- 🌐 **Browser Provider**: Web page fetching, HTML text extraction, URL status checks, and launching Windows default web browser.
- 🛡️ **Security Guardrails**: Strict path-traversal sandboxing, read-only mode, command allowlisting, destructive command confirmation, and audit logging.

---

## Architecture & Security Model

```
                    ┌────────────────────────┐
                    │       MCP Client       │
                    │ (LM Studio / Claude)   │
                    └───────────┬────────────┘
                                │ JSON-RPC (stdio)
                                ▼
                    ┌────────────────────────┐
                    │      server.py         │
                    │   (FastMCP Engine)     │
                    └───────────┬────────────┘
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
┌──────────────────┐                       ┌──────────────────┐
│  Security Layer  │                       │ ProviderRegistry │
│  - Path Sandbox  │                       └────────┬─────────┘
│  - Command Audit │                                │ Auto-Discovers
│  - Read-Only     │                                ▼
└──────────────────┘                       ┌──────────────────┐
                                           │  12 Providers    │
                                           │  (40+ Tools)     │
                                           └──────────────────┘
```

### Security Features
1. **Workspace Sandboxing**: All file read/write operations are constrained to the configured workspace root (`workspace.path`). Path traversal outside the workspace triggers `WorkspaceViolationError`.
2. **Command Validation**: Built-in regex filters block destructive OS commands (`format`, `del /f /s /q C:\*`, `shutdown`, `reg delete`, `Set-ExecutionPolicy Bypass`).
3. **Read-Only Mode**: Setting `read_only = true` in `config.toml` instantly converts the server into a non-destructive inspection tool.
4. **Destructive Command Confirmation**: Commands altering filesystem state require explicit `confirm = true` parameter flags.
5. **Audit Logging**: All tool invocations and security checks are recorded to rotated logs in `logs/`.

---

## Installation

### Prerequisites
- **Windows 10 / 11** or **Windows Server 2019+**
- **Python 3.12+**

### 1. Clone & Setup Virtual Environment
```powershell
git clone https://github.com/your-org/windows-developer-mcp.git
cd windows-developer-mcp

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Package with Dev Dependencies
```powershell
pip install -e .[dev]
```

Or using [uv](https://github.com/astral-sh/uv):
```powershell
uv pip install -e .[dev]
```

---

## Configuration

The server is configured via `config.toml` in the project root:

```toml
[server]
name = "Windows Developer MCP"
version = "0.1.0"

[workspace]
path = "."                  # Root directory for file operations
read_only = false           # Set to true to block all modifications

[security]
timeout = 60                # Default command execution timeout (seconds)
require_confirmation = true # Require confirm=true for destructive actions
max_output_length = 50000   # Maximum characters returned per tool execution

[providers]
terminal   = true
filesystem = true
git        = true
python     = true
node       = true
docker     = true
windows    = true
network    = true
sqlite     = true
project    = true
github     = true
browser    = true
```

---

## Integration with MCP Clients

### LM Studio Configuration
Add to your LM Studio `mcp_config.json`:

```json
{
  "mcpServers": {
    "windows-developer-mcp": {
      "command": "C:\\Users\\<YourUsername>\\terminal-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\<YourUsername>\\terminal-mcp\\server.py"]
    }
  }
}
```

### Claude Desktop Configuration
Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "windows-developer-mcp": {
      "command": "C:\\Users\\<YourUsername>\\terminal-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\<YourUsername>\\terminal-mcp\\server.py"]
    }
  }
}
```

---

## Provider & Tool Matrix

| Provider | Tools Included | Description |
| :--- | :--- | :--- |
| **Terminal** | `run_powershell`, `run_cmd`, `get_working_directory`, `set_working_directory` | Execute shell commands safely with timeouts & CWD control. |
| **Filesystem** | `read_file`, `write_file`, `list_directory`, `tree`, `file_exists`, `file_info`, `search_files`, `hash_file` | Read, write, list, search, and hash files within workspace bounds. |
| **Git** | `git_status`, `git_log`, `git_branch`, `git_diff` | Inspect git repository status, history, branches, and diffs. |
| **Python** | `python_version`, `pip_version`, `check_package` | Environment info and package availability checks. |
| **Node** | `node_version`, `npm_version`, `package_info` | Inspect Node runtime, npm version, and `package.json` details. |
| **Docker** | `docker_info`, `list_containers`, `container_logs` | Container inspection and log retrieval. |
| **Windows** | `system_info`, `list_processes`, `environment_variables` | Process listing, OS details, and env var inspection. |
| **Network** | `ping`, `dns_lookup`, `check_port`, `fetch_headers` | Connectivity testing and DNS lookup utilities. |
| **SQLite** | `sqlite_tables`, `sqlite_schema`, `sqlite_query` | Query and inspect local SQLite database files. |
| **Project** | `detect_project_type`, `analyze_structure` | Auto-detect framework & generate project summaries. |
| **GitHub** | `search_repos`, `list_issues`, `list_prs`, `get_release` | GitHub API / `gh` CLI repository integrations. |
| **Browser** | `open_url`, `fetch_page`, `extract_text`, `check_url` | Web page fetching, clean text extraction, and browser opening. |

---

## Testing & Quality Assurance

Run the full test suite using `pytest`:
```powershell
.\.venv\Scripts\pytest.exe -v
```

Run code formatting and linting audit:
```powershell
.\.venv\Scripts\ruff.exe check .
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
