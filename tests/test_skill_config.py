from __future__ import annotations

from pathlib import Path


class TestSkillConfig:
    def test_skill_md_exists_and_has_sections(self):
        skill_dir = Path(__file__).parent.parent / "skills" / "openrouter-agent"
        skill_path = skill_dir / "SKILL.md"
        assert skill_path.exists(), "SKILL.md missing"
        content = skill_path.read_text(encoding="utf-8")
        assert "openrouter-agent" in content
        assert "benchmarks.py" in content
        assert "tools/MCP/" in content

    def test_readme_exists(self):
        skill_dir = Path(__file__).parent.parent / "skills" / "openrouter-agent"
        assert (skill_dir / "README.md").exists()
        assert (skill_dir / "install-all.md").exists()

    def test_harness_guides_exist(self):
        skill_dir = Path(__file__).parent.parent / "skills" / "openrouter-agent"
        for name in ("claude.md", "codex.md", "hermes.md", "opencode.md", "cursor.md"):
            assert (skill_dir / "harness" / name).exists(), f"harness/{name} missing"

    def test_prompt_templates_reference_cli(self):
        skill_dir = Path(__file__).parent.parent / "skills" / "openrouter-agent"
        for name in ("benchmark-search.md", "model-recommend.md"):
            path = skill_dir / "prompts" / name
            assert path.exists(), f"prompts/{name} missing"
            content = path.read_text(encoding="utf-8")
            assert "benchmarks.py" in content, f"{name} missing CLI reference"

    def test_validate_config_script_exists(self):
        skill_dir = Path(__file__).parent.parent / "skills" / "openrouter-agent"
        assert (skill_dir / "validate_config.py").exists()
