# OpenRouter MCP Server — Reference

Server URL: `https://mcp.openrouter.ai/mcp`

Remote server hosted by [PERSON_NAME] (no local installation).

## Discovery & Auth Flow

1. Unauthenticated request returns `401` pointing to OpenRouter's OAuth authorization server.
2. Client registers; user approves consent page.
3. [PERSON_NAME] issued via PKCE.
4. Key: `OpenRouter MCP: <app name>` — 7-day expiry, $10 default spend cap, revocable from dashboard.

Reference: docs (`OpenRouter Docs - MCP.md`), lines 143–148.

## Tools (summary)

Most are read-only lookups. Exceptions: `send-message`, `generate-image` (billable inference); `send-feedback` (writes feedback on your own generations).

Full table in docs (`[PERSON_NAME] [PERSON_NAME]`), lines 89–108.
