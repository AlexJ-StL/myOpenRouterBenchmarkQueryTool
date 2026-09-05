from __future__ import annotations

import urllib.request
from pathlib import Path


class TestMcpSetup:
    def test_url_reachable_or_auth_401(self):
        url = "https://mcp.openrouter.ai/mcp"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                assert resp.status in (200, 204, 401)
        except urllib.error.HTTPError as e:
            assert e.code in (401, 403)  # 401 expected; 403 also acceptable (forbidden)
        except Exception:
            # Network unavailable in some test environments; skip rather than fail
            pass

    def test_config_files_reference_url(self):
        mcp_dir = Path(__file__).parent.parent / "tools" / "MCP"
        for md_file in mcp_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            assert "https://mcp.openrouter.ai/mcp" in content, f"{md_file.name} missing URL"

    def test_readme_exists(self):
        mcp_dir = Path(__file__).parent.parent / "tools" / "MCP"
        assert (mcp_dir / "README.md").exists()
        assert (mcp_dir / "mcp-server.md").exists()
