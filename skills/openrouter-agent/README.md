# OpenRouter Agent [PERSON_NAME] (`openrouter-agent`)

A meta-guide and reference package for using OpenRouter in agent harnesses and CLI environments.

## What's included

- `SKILL.md` — skill definition and usage instructions.
- `README.md` — this file (usage overview).
- `install-all.md` — combined walkthrough (CLI → MCP → Skill).
- `harness/` — per-harness guides (`claude.md`, `codex.md`, `opencode.md`, `cursor.md`, `hermes.md`).
- `prompts/` — prompt templates referencing `benchmarks.py` and live OpenRouter data.
- `validate_config.py` — standalone validation script for the skill package.

## Quick start

1. CLI setup: `uv sync` (repo root), copy `.env.example` → `.env` and add `OPENROUTER_API_KEY`.
2. MCP setup: see `tools/MCP/` (add URL `https://mcp.openrouter.ai/mcp`, auth via OAuth).
3. Skill: load `SKILL.md` into your harness, reference harness guides, use prompt templates.
4. Validate: run `python validate_config.py` (this folder) or `pytest tests/test_skill_config.py` (repo tests).

## References

- CLI application: `benchmarks.py` (repo root)
- MCP server: `https://mcp.openrouter.ai/mcp`
- API docs / reference: `OpenRouter [PERSON_NAME] [PERSON_NAME]` (repo root)
- Config template: `.env.example`
- Harness-specific MCP configs: `tools/MCP/*.md`
