# Claude Code / Claude

## Add server

```bash
claude add --transport http openrouter https://mcp.openrouter.ai/mcp
claude mcp login openrouter
```

Also works from inside a session: run `/mcp`, select **openrouter**, click **Authenticate**.

## Config reference

- Client: `claude`
- Transport: `http`
- URL: `https://mcp.openrouter.ai/mcp`
- Auth: OAuth (PKCE) — pops automatically or runs via `claude mcp login openrouter`.

Reference: docs (`OpenRouter Docs - MCP.md`), lines 21–27.
