# LM Studio Integration Guide — Windows Developer MCP Server

This guide explains how to connect **Windows Developer MCP** with **LM Studio** for local LLM execution (Qwen 2.5, DeepSeek R1, Llama 3, Gemma).

---

## 1. Prerequisites
- [LM Studio](https://lmstudio.ai/) installed on Windows.
- Python 3.12+ and `uv` installed.

## 2. Configuration Setup

Add the following entry to your LM Studio MCP server configuration JSON file (usually located under `~/.lmstudio/mcp_config.json` or configured in the LM Studio UI settings):

```json
{
  "mcpServers": {
    "windows-developer-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\Peeyush\\terminal-mcp",
        "run",
        "windows-developer-mcp"
      ],
      "env": {
        "MCP_SERVER__PROFILE": "minimal",
        "MCP_WORKSPACE__PATH": "C:\\Users\\Peeyush\\projects"
      }
    }
  }
}
```

---

## 3. Profile Recommendation for Local Models

| Model Size | Recommended Profile | Context Token Footprint | Description |
|---|---|---|---|
| **7B / 8B** | `minimal` | ~1.2K tokens | Exposes ~8 core tools + meta-search. Optimal context budget. |
| **14B / 32B** | `developer` | ~3.8K tokens | Exposes ~25 core developer tools. |
| **70B+ / Cloud** | `full` | ~12K tokens | Exposes complete fine-grained tool suite across all 12 providers. |
