# Provider Documentation — Windows Developer MCP Server

Windows Developer MCP contains 12 domain-specific providers designed under strict Single Responsibility principles.

---

## Provider Reference

### 1. TerminalProvider (`providers/terminal.py`)
- **Responsibility**: Safe PowerShell and CMD command execution within workspace bounds.
- **Key Tools**:
  - `terminal_run`: Execute shell commands with timeout guards.
  - `terminal_get_session`: Inspect current directory and execution environment.

### 2. FilesystemProvider (`providers/filesystem.py`)
- **Responsibility**: Workspace-restricted file reading, writing, searching, and metadata inspection.
- **Key Tools**:
  - `filesystem_read`: Read text file content safely.
  - `filesystem_write`: Create or edit files inside workspace.
  - `filesystem_list`: List directory contents with metadata.
  - `filesystem_search`: Find files by pattern or glob.

### 3. GitProvider (`providers/git.py`)
- **Responsibility**: Git repository status, commits, branches, and diff inspection.
- **Key Tools**:
  - `git_status`: Query working tree state.
  - `git_log`: View commit history.
  - `git_diff`: Show file modifications.

### 4. PythonProvider (`providers/python.py`)
- **Responsibility**: Python virtual environment inspection and script execution.
- **Key Tools**:
  - `python_run`: Execute Python scripts within virtualenv context.
  - `python_check_package`: Verify installed package versions.

### 5. NodeProvider (`providers/node.py`)
- **Responsibility**: Node.js and NPM package management.
- **Key Tools**:
  - `node_run`: Run Node.js scripts.
  - `npm_run`: Execute npm lifecycle scripts.

### 6. DockerProvider (`providers/docker.py`)
- **Responsibility**: Container, image, and service orchestration via Docker CLI.
- **Key Tools**:
  - `docker_ps`: List running containers.
  - `docker_logs`: Fetch container log output.

### 7. WindowsProvider (`providers/windows.py`)
- **Responsibility**: Windows system metrics, process management, and environment variables.
- **Key Tools**:
  - `windows_system_info`: CPU, memory, OS, and drive usage.
  - `windows_list_processes`: Inspect running processes.

### 8. NetworkProvider (`providers/network.py`)
- **Responsibility**: Diagnostic network queries.
- **Key Tools**:
  - `network_ping`: Check host connectivity.
  - `network_dns_lookup`: Resolve domain IP addresses.

### 9. SQLiteProvider (`providers/sqlite.py`)
- **Responsibility**: SQLite database query and schema inspection.
- **Key Tools**:
  - `sqlite_query`: Execute read-only SQL queries.
  - `sqlite_schema`: Introspect database tables and columns.

### 10. ProjectProvider (`providers/project.py`)
- **Responsibility**: AI project analysis, security scanning, documentation generation, and test creation.
- **Key Tools**:
  - `project_analyze`: Tech stack identification.
  - `project_dependencies`: Dependency tree analyzer.
  - `project_summarize`: File tree summary.
  - `project_architecture`: Software design pattern inspection.
  - `project_generate_readme`: Automated README builder.
  - `project_generate_docs`: AST API doc extractor.
  - `project_security_scan`: Static secret and vulnerability scanner.
  - `project_generate_tests`: Pytest skeleton generator.

### 11. GitHubProvider (`providers/github.py`)
- **Responsibility**: GitHub CLI wrapper for PRs, issues, and repositories.

### 12. BrowserProvider (`providers/browser.py`)
- **Responsibility**: Browser automation interface (disabled by default).
