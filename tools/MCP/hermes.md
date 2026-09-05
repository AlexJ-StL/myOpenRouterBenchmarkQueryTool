# Hermes Harness

Hermes is not explicitly covered in the OpenRouter docs. Use the standard remote MCP URL and OAuth flow.

## Setup (best practice)

1. Configure the remote MCP server in your Hermes harness config:

```json
{
  "mcpServers": {
    "openrouter": {
      "url": "https://mcp.openrouter.ai/mcp",
      "type": "remote"
    }
  }
}
```

2. Trigger authentication (either automatic on first tool use or manual via your harness's MCP login command).
3. Verify the connection responds (see `test_setup.py`).

Reference: standard remote MCP pattern (`tools/MCP/README.md`); auth flow from docs (`OpenRouter Docs - MCP.md`), lines 83–84.
