# Usage Examples — Windows Developer MCP Server

Practical workflow examples using **Windows Developer MCP**.

---

## Example 1: AI Project Analysis & Documentation Generation

### Step 1: Analyze Workspace Tech Stack
```json
// Tool: project_analyze
{}
```

### Step 2: Extract API Documentation
```json
// Tool: project_generate_docs
{
  "file_path": "core/config.py"
}
```

### Step 3: Scan Project for Security Findings
```json
// Tool: project_security_scan
{}
```

---

## Example 2: Terminal & Git Workflow

### Step 1: Query Git Status
```json
// Tool: git_status
{}
```

### Step 2: Run PowerShell Diagnostics
```json
// Tool: terminal_run
{
  "command": "Get-Service | Where-Object Status -eq 'Running'"
}
```

---

## Example 3: Context-Aware Dynamic Provider Activation (Minimal Profile)

When running under `MINIMAL` profile with a 7B local model in LM Studio:

```json
// Step 1: Search available capabilities
// Tool: mcp_search_tools
{
  "query": "docker"
}

// Step 2: Enable docker provider dynamically
// Tool: mcp_enable_provider
{
  "provider_name": "docker"
}
```
