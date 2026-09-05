# OpenCode

Add this to `~/.config/opencode/opencode.json`. OpenCode runs the OAuth flow automatically on first use — no separate login step.

```json
{
  "mcp": {
    "openrouter": {
      "type": "remote",
      "url": "https://mcp.openrouter.ai/mcp",
      "enabled": true
    }
  }
}
```

Reference: docs (`OpenRouter Docs - MCP.md`), lines 38–50.
