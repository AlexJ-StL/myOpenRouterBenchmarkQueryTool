# Cursor CLI / Cursor IDE

The Cursor CLI (`cursor-agent`) reads the same config as the IDE. Add to `~/.cursor/mcp.json`, then verify with `cursor-agent mcp list`. Authenticate from Cursor MCP settings, or it prompts on first tool use.

```json
{
  "mcpServers": {
    "openrouter": {
      "url": "https://mcp.openrouter.ai/mcp"
    }
  }
}
```

Reference: docs (`OpenRouter Docs - MCP.md`), lines 53–63.
