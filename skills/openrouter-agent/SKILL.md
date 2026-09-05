# OpenRouter Agent Skill

Name: `openrouter-agent`

Description: Meta-guide and reference package for using OpenRouter in agent harnesses and CLI environments. Provides harness-specific setup guides, prompt templates referencing live OpenRouter data, and validation scripts. References the existing `benchmarks.py` CLI (in repo root) rather than duplicating it.

Usage:

1. Ensure the CLI is installed (`uv sync` in repo root) and `.env` is configured with `OPENROUTER_API_KEY`.
2. Set up the MCP server (`tools/MCP/` — add URL, complete OAuth).
3. Load the skill into your harness (load `SKILL.md` or reference harness guides).
4. Use prompt templates (`prompts/`) to invoke benchmark queries or model recommendations via the CLI.
5. Validate with `validate_config.py` (in this folder) or `tests/test_skill_config.py`.

References:

- CLI: `benchmarks.py` (repo root)
- MCP server: `https://mcp.openrouter.ai/mcp` (`tools/MCP/`)
- API docs: `OpenRouter Docs - MCP.md` (repo root)
- Config template: `.env.example`
