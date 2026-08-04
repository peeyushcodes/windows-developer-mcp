# Windows Developer MCP Server

[![Glama Indexed](https://img.shields.io/badge/Glama-Indexed-blue.svg?style=for-the-badge&logo=glama)](https://glama.ai/mcp/servers)
[![CI Pipeline](https://img.shields.io/github/actions/workflow/status/peeyushcodes/windows-developer-mcp/ci.yml?branch=main&style=for-the-badge&logo=github)](https://github.com/peeyushcodes/windows-developer-mcp/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-green.svg?style=for-the-badge&logo=python)](https://python.org)
[![FastMCP v2.0+](https://img.shields.io/badge/FastMCP-v2.0+-orange.svg?style=for-the-badge)](https://github.com/jlowin/fastmcp)
[![Ruff](https://img.shields.io/badge/Code%20Style-Ruff-000000.svg?style=for-the-badge&logo=ruff)](https://github.com/astral-sh/ruff)
[![Basedpyright](https://img.shields.io/badge/Type%20Checker-Basedpyright-blueviolet.svg?style=for-the-badge)](https://github.com/detachhead/basedpyright)

**Windows Developer MCP** gives AI assistants (**Claude Desktop**, **LM Studio**, **Cursor**, etc.) safe, native developer superpowers on Windows — including terminal execution, Git/GitHub integration, Docker management, filesystem operations, and AI project diagnostics.

---

## ⚡ 1-Minute Quick Start

### Step 1: Install `uv`
If you don't have `uv` installed, open PowerShell and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 2: Configure Your AI Client

#### 🤖 Claude Desktop Setup
Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "windows-developer-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\path\\to\\windows-developer-mcp",
        "run",
        "windows-developer-mcp"
      ],
      "env": {
        "MCP_SERVER__PROFILE": "developer",
        "MCP_WORKSPACE__PATH": "C:\\path\\to\\your\\project"
      }
    }
  }
}
```

#### 💻 LM Studio / Local LLM Setup
Edit your LM Studio MCP server configuration:

```json
{
  "mcpServers": {
    "windows-developer-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\path\\to\\windows-developer-mcp",
        "run",
        "windows-developer-mcp"
      ],
      "env": {
        "MCP_SERVER__PROFILE": "minimal",
        "MCP_WORKSPACE__PATH": "C:\\path\\to\\your\\project"
      }
    }
  }
}
```

---

## 🔥 Key Features

- **🛡️ Workspace-Confined & Sandboxed**: All commands are executed securely with strict path normalization, denylists, and audit logging.
- **⚡ Dual-Profile Engine**:
  - **`minimal`**: Optimized for **Local LLMs (7B/8B)** in LM Studio (<1.2K token context footprint).
  - **`developer`**: Ideal for **Claude Desktop / GPT-4o** (~3.8K token footprint).
  - **`full`**: Complete exposure for **70B+ LLMs & Glama Indexing**.
- **🧰 40+ Developer Tools across 12 Modules**: Terminal, Git, GitHub, Docker, Filesystem, Python, Node, SQLite, Windows, Network, Browser, and AI Project Analysis.

---

## 🧰 Available Tool Modules

| Module | Core Tools Exposed | Description |
| :--- | :--- | :--- |
| **Terminal** | `terminal_run`, `terminal_get_session` | Safe PowerShell & CMD subprocess execution. |
| **Filesystem** | `filesystem_read`, `filesystem_write`, `filesystem_list` | Workspace-restricted file & directory operations. |
| **Git** | `git_status`, `git_log`, `git_diff`, `git_commit`, `git_push` | Git branch, commit, diff, and remote management. |
| **GitHub** | `github_auth_status`, `github_repo_info`, `github_list_issues`, `github_list_prs` | GitHub API for repos, PRs, issues, and releases. |
| **Docker** | `docker_list_containers`, `docker_logs`, `docker_run`, `docker_build` | Container, image, and Compose orchestration. |
| **Python** | `python_run`, `python_check_package`, `python_install_package` | Virtual environment management & execution. |
| **Node.js** | `node_run`, `npm_run`, `npm_install` | Node.js script execution & npm package management. |
| **SQLite** | `sqlite_query`, `sqlite_schema`, `sqlite_list_tables`, `sqlite_execute` | Database queries & schema inspection. |
| **Windows** | `windows_system_info`, `windows_list_processes`, `windows_get_env` | System metrics, process list, and environment vars. |
| **Network** | `network_ping`, `network_dns_lookup`, `network_port_scan` | Network diagnostics & connectivity checks. |
| **Project (AI)** | `project_analyze`, `project_security_scan`, `project_generate_readme` | Tech stack detection, security audit, & code gen. |
| **Browser** | `browser_open_url`, `browser_fetch_page`, `browser_extract_text` | Web page fetching & clean text extraction. |

---

## 🧠 AI-Native Project Analysis Tools

`ProjectProvider` provides intelligent tools designed specifically for codebase comprehension:

- 🔍 **`project_analyze`**: Auto-detects frameworks, tech stacks, and entry points.
- 🛡️ **`project_security_scan`**: Static audit for hardcoded API keys, tokens, and credentials.
- 🌳 **`project_summarize`**: Hierarchical directory tree generator.
- 📦 **`project_dependencies`**: Cross-language dependency analysis.
- 📝 **`project_generate_readme`**: Drafts a complete README.md based on codebase analysis.
- 🧪 **`project_generate_tests`**: Generates pytest unit test skeletons for source files.

---

## 🛡️ Safety & Security Features

1. **Workspace Boundary Sandbox**: Operations are strictly restricted to the specified workspace path (`MCP_WORKSPACE__PATH`).
2. **Command Denylist**: Blocks dangerous operations (`format`, `shutdown`, `del /f /s /q`, etc.).
3. **Audit Logging**: All executed actions are recorded in `logs/audit.log`.

---

## 📚 Documentation Suite

- 📐 [Architecture Overview](docs/architecture.md)
- 🔌 [Provider Reference](docs/providers.md)
- 🛡️ [Security Model](docs/security.md)
- 🤖 [LM Studio Setup Guide](docs/lm_studio_setup.md)
- 🖥️ [Claude Desktop Setup Guide](docs/claude_desktop_setup.md)
- 🤝 [Contributing Guide](docs/contributing.md)
- 📋 [Glama Manifest (glama.json)](glama.json)
- 📜 [Changelog](CHANGELOG.md)

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.
