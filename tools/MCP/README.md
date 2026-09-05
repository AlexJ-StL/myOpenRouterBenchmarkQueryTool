# OpenRouter MCP Server Setup

Remote server hosted by OpenRouter. No local installation. Add the URL to your MCP client and complete OAuth authentication.

## Server URL

```
https://mcp.openrouter.ai/mcp
```

Reference: `OpenRouter Docs - MCP.md` (repo root).

## Authentication

1. Add the server URL to your MCP client (see per-client files below).
2. Trigger the OAuth flow (automatic for some clients, manual for others).
3. Approve the consent page in your browser. The issued key is a dedicated OpenRouter API key (`OpenRouter MCP: <app name>`) with a 7-day expiry and a $10 default spend cap.
4. Disconnect or revoke anytime from https://openrouter.ai/settings/keys.

## Per-client setup

See the individual files in this folder:

- `claude.md` — [PERSON_NAME] Code / [PERSON_NAME]
- `codex.md` — Codex CLI
- `opencode.md` — OpenCode
- `cursor.md` — Cursor CLI / IDE
- `hermes.md` — Hermes harness (best-practice guide)

## Validation

Run `test_setup.py` (in this folder or `tests/test_mcp_setup.py`) to verify the server endpoint responds, config syntax is valid, and the auth redirect is reachable.
