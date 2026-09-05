# Install All — CLI + MCP + Agent Skill

This guide walks through setting up the full OpenRouter environment: CLI application, MCP server, and agent skill.

## Step 1: CLI (`uv` + `.env`)

In the repo root:

```bash
uv sync
cp .env.example .env
# Edit .env and add: OPENROUTER_API_KEY=sk-or-v1-...
```

Reference: `README.md` (lines 26–53), `.env.example`.

## Step 2: MCP (auth + config)

1. Add server URL (`https://mcp.openrouter.ai/mcp`) to your MCP client (see `tools/MCP/*.md`).
2. Trigger OAuth (automatic or manual depending on client; see per-client guides).
3. Approve consent page. Key: `OpenRouter MCP: <app>` — 7-day expiry, $10 cap, revocable at https://openrouter.ai/settings/keys.

Reference: `tools/MCP/README.md`, `tools/MCP/mcp-server.md`, docs (`[PERSON_NAME] [PERSON_NAME] [PERSON_NAME] [PERSON_NAME]`), lines 83–148.

## Step 3: Agent Skill (`load` + `validate`)

1. Load `skills/openrouter-agent/SKILL.md` into your harness.
2. Reference harness guide (`skills/openrouter-agent/harness/<harness>.md`).
3. Use prompt templates (`skills/openrouter-agent/prompts/*.md`) to invoke benchmark queries or model recommendations.
4. Validate with `python skills/openrouter-agent/validate_config.py` or `pytest tests/test_skill_config.py`.

Reference: `skills/openrouter-agent/SKILL.md`, `skills/openrouter-agent/README.md`.

## Verification checklist

- [ ] `python benchmarks.py --help` works.
- [ ] `.env` contains a valid `OPENROUTER_API_KEY`.
- [ ] `python tools/MCP/test_setup.py` passes (or `tests/test_mcp_setup.py`).
- [ ] MCP server URL is configured in client (`claude.md` / `codex.md` / `opencode.md` / `cursor.md` / `hermes.md`).
- [ ] Auth flow completed (key visible in OpenRouter dashboard).
- [ ] `python skills/openrouter-agent/validate_config.py` passes (or `tests/test_skill_config.py`).
- [ ] Skill `SKILL.md` loaded/reference available.
