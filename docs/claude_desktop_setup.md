# Claude Desktop Integration Guide — Windows Developer MCP Server

This guide details how to integrate **Windows Developer MCP** with **Claude Desktop** on Windows.

---

## Configuration File Location

Locate your Claude Desktop config file:
`%APPDATA%\Claude\claude_desktop_config.json`

Add the server definition:

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
        "MCP_SERVER__PROFILE": "developer",
        "MCP_WORKSPACE__PATH": "."
      }
    }
  }
}
```

Restart Claude Desktop to activate tools.
