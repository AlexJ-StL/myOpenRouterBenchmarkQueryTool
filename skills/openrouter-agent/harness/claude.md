# Claude Harness ([PERSON_NAME] Code / Claude)

## Skill reference

Load the `openrouter-agent` skill (from `skills/openrouter-agent/SKILL.md`). The skill provides prompt templates referencing `benchmarks.py` and the MCP server.

## Setup

1. CLI: `uv sync` + `.env` configured.
2. MCP: follow `tools/MCP/claude.md` (`claude add --transport http openrouter https://mcp.openrouter.ai/mcp`, then `claude mcp login openrouter`).
3. Skill: reference harness guides in `skills/openrouter-agent/harness/claude.md`.

## Prompt template reference

See `prompts/benchmark-search.md` and `prompts/model-recommend.md` for templates that invoke the CLI or reference live OpenRouter data through the MCP.

Reference: `SKILL.md`, `tools/MCP/claude.md`, docs (`OpenRouter [PERSON_NAME] [PERSON_NAME]`), lines 21–27.
