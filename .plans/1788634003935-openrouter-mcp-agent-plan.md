# Plan: OpenRouter MCP + Agent Skill Setup

## Decisions (resolved)
- Folders: `tools/MCP/` and `skills/openrouter-agent/` (separate, not nested).
- Agent skill: meta-guide/reference package (`SKILL.md` + harness guides + prompts + `README.md`). References existing `benchmarks.py`; no tool wrapper duplication.
- `SKILL.md`: new design format (`name`/`description`/`usage`/`harness-guides`/`references`).
- Testing: extend `tests/` (`test_mcp_setup.py`, `test_skill_config.py`) + folder-level validation scripts (`validate_config.py` in skill, `test_setup.sh`-style or `.py` in MCP).
- `install-all.md`: CLI (`uv sync` + `.env`) → MCP (`auth` + config templates) → Skill (`load` + `validate`).

## Folder structure (to create)
```
tools/MCP/
  README.md              # Setup instructions + URL reference (https://mcp.openrouter.ai/mcp)
  mcp-server.md           # Auth-flow reference (from OpenRouter Docs - MCP.md)
  claude.md                # Claude Code / Claude Desktop config + auth
  codex.md                 # Codex CLI config + auth
  opencode.md              # OpenCode (`opencode.json`) config
  cursor.md                # Cursor (`mcp.json`) config + CLI verification
  hermes.md                # Hermes harness guide (user-requested, no docs file reference; include best-practice setup)
  test_setup.py            # Python validation: URL reachable, config syntax valid, auth endpoint responds
skills/openrouter-agent/
  SKILL.md                 # Skill definition (new format)
  README.md                # Skill usage + reference to CLI
  install-all.md           # Combined walkthrough (CLI→MCP→Skill)
  harness/
    claude.md              # Prompt/reference guide for Claude
    codex.md               # Prompt/reference guide for Codex
    hermes.md              # Prompt/reference guide for Hermes
    opencode.md            # Prompt/reference guide for OpenCode
    cursor.md              # Prompt/reference guide for Cursor
  prompts/
    benchmark-search.md    # Template prompt referencing benchmarks.py flags
    model-recommend.md     # Template for model selection via live data
  validate_config.py       # Skill config/check syntax validation
```

## Testing plan
- `tests/test_mcp_setup.py`: validates `https://mcp.openrouter.ai/mcp` responds, config JSON syntax, and auth endpoint returns 401→consent redirect.
- `tests/test_skill_config.py`: validates `SKILL.md` structure, harness guides reference existing CLI, prompts contain expected reference keywords.
- `skills/openrouter-agent/validate_config.py`: standalone script to check skill package completeness.
- `tools/MCP/test_setup.py`: validates per-client config templates (`claude.md`, `codex.md`, etc.) are syntactically correct and reference correct URL/auth steps.

## References used
- `OpenRouter Docs - MCP.md` (repo root): MCP server URL, auth flow, per-client instructions, tool list.
- `README.md`: CLI usage (`benchmarks.py`), `.env`, `uv sync`, benchmark flags.
- `.env.example`: key setup reference.
- Existing repo structure: `.kilo/`, `tests/`, `pyproject.toml`.

## Open / out of scope
- No new CLI tool wrapper (skill is meta-guide only).
- No duplicate `benchmarks.py` code; references only.
- No deployment automation; only local setup files + validation scripts.
- `hermes.md` has no docs reference; will include best-practice harness guide based on general agent harness patterns.
