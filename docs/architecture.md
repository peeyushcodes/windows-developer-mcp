# Architecture Overview — Windows Developer MCP Server

This document outlines the architecture, design principles, and component interactions of **Windows Developer MCP**.

---

## 1. High-Level Architecture Diagram

```
+-------------------------------------------------------------------------------+
|                       MCP Client (LM Studio / Claude Desktop)                  |
+-------------------------------------------------------------------------------+
                                        | (STDIO / JSON-RPC)
                                        v
+-------------------------------------------------------------------------------+
|                             FastMCP Framework Application                     |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                      Provider Registry (core/registry.py)                      |
|  - Server Profile Filter: [ MINIMAL | DEVELOPER | FULL ]                       |
|  - Meta-Tools: mcp_search_tools, mcp_list_profiles, mcp_enable_provider       |
+-------------------------------------------------------------------------------+
                                        |
       +--------------------------------+--------------------------------+
       |                                |                                |
       v                                v                                v
+----------------------+     +----------------------+     +----------------------+
| TerminalProvider     |     | FilesystemProvider   |     | ProjectProvider      |
| GitProvider          |     | SQLiteProvider       |     | Security Scan        |
| Python / Node        |     | DockerProvider       |     | AI Docs & Tests Gen  |
+----------------------+     +----------------------+     +----------------------+
       |                                |                                |
       +--------------------------------+--------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                           Security Execution Layer                            |
|  - Workspace Sandbox (security/sandbox.py)                                    |
|  - Command Validator & Allowlist/Denylist (security/validator.py)              |
|  - Rate Limiter (security/rate_limiter.py)                                    |
|  - Audit Logger (security/logger.py)                                          |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                           Windows OS Subprocess Subsystem                     |
|                        (PowerShell 7+ / Cmd / Process Pool)                   |
+-------------------------------------------------------------------------------+
```

---

## 2. Core Architectural Principles

1. **Single Responsibility Principle (SRP)**:
   - Each provider in `providers/` handles exactly one domain (e.g. Git, Docker, Terminal, SQLite).
   - No bloated monolithic provider files.

2. **Dual-Profile Tool Exposure Architecture**:
   - `MINIMAL`: Exposes ~8-12 core tools to keep system prompt context usage <2K tokens for 7B/8B local models in LM Studio.
   - `DEVELOPER`: Exposes ~25 primary developer tools.
   - `FULL`: Exposes all fine-grained tools for complete API coverage and Glama auditing.

3. **Capability Negotiation & Dynamic Meta-Tools**:
   - `mcp_search_tools`: Search capabilities on demand without bloating system prompts.
   - `mcp_enable_provider`: Dynamically register/activate domain providers on demand.

4. **Defense in Depth Security**:
   - Path normalization prevents directory traversal out of the workspace sandbox.
   - Execution validation blocks dangerous PowerShell / CMD command injections.
   - Audit logging produces structured JSON records for all executions.
