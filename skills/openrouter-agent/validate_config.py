#!/usr/bin/env python3
"""Validate agent skill package (`skills/openrouter-agent`).

Checks:
- SKILL.md exists and contains required sections.
- Harness guides reference the CLI and MCP setup.
- Prompt templates reference `benchmarks.py` flags or live data.
- README.md exists.
- install-all.md exists.
"""

from pathlib import Path

SKILL_DIR = Path(__file__).parent
REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "install-all.md",
    "validate_config.py",
]
HARNESS_GUIDES = [
    "harness/claude.md",
    "harness/codex.md",
    "harness/hermes.md",
    "harness/opencode.md",
    "harness/cursor.md",
]
PROMPT_TEMPLATES = [
    "prompts/benchmark-search.md",
    "prompts/model-recommend.md",
]


def validate():
    ok = True
    for f in REQUIRED_FILES:
        path = SKILL_DIR / f
        if not path.exists():
            print(f"FAIL: missing {f}")
            ok = False
        else:
            print(f"OK: {f}")

    for h in HARNESS_GUIDES:
        path = SKILL_DIR / h
        if not path.exists():
            print(f"FAIL: missing harness guide {h}")
            ok = False
        else:
            content = path.read_text(encoding="utf-8")
            if "benchmarks.py" not in content and "https://mcp.openrouter.ai/mcp" not in content:
                print(f"WARN: {h} missing CLI or MCP reference")
            else:
                print(f"OK: {h}")

    for p in PROMPT_TEMPLATES:
        path = SKILL_DIR / p
        if not path.exists():
            print(f"FAIL: missing prompt {p}")
            ok = False
        else:
            content = path.read_text(encoding="utf-8")
            if "benchmarks.py" not in content:
                print(f"WARN: {p} missing CLI reference")
            else:
                print(f"OK: {p}")

    # SKILL.md content checks
    skill_path = SKILL_DIR / "SKILL.md"
    if skill_path.exists():
        content = skill_path.read_text(encoding="utf-8")
        required = ["openrouter-agent", "SKILL.md", "benchmarks.py", "tools/MCP/"]
        missing = [r for r in required if r not in content]
        if missing:
            print(f"WARN: SKILL.md missing references: {', '.join(missing)}")
        else:
            print("OK: SKILL.md references correct")

    return ok


if __name__ == "__main__":
    if validate():
        print("\nAgent skill package validation passed.")
    else:
        print("\nAgent skill package validation failed.")
        exit(1)
