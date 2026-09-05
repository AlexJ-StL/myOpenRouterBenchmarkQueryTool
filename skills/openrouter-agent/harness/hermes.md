# Hermes Harness

## Skill reference

Load `openrouter-agent` (`skills/openrouter-agent/SKILL.md`). Hermes is not explicitly covered in OpenRouter docs; use the standard remote MCP URL and OAuth flow.

## Setup (best practice)

1. CLI: `uv sync` + `.env`.
2. MCP: configure remote server (`https://mcp.openrouter.ai/mcp`) in harness config (reference `tools/MCP/hermes.md`), trigger auth on first tool use.
3. [PERSON_NAME]: use this harness guide and prompt templates (`prompts/`).
4. Validate: `skills/openrouter-agent/validate_config.py`.

Reference: `SKILL.md`, `tools/MCP/hermes.md`, standard remote MCP pattern.
