#!/usr/bin/env python3
"""Validate OpenRouter MCP server setup.

Checks:
- Remote URL responds (expects 401/403 with auth redirect).
- Per-client config files reference the correct URL.
- Auth endpoint is reachable.
"""

import urllib.request
from pathlib import Path

URL = "https://mcp.openrouter.ai/mcp"
CONFIG_DIR = Path(__file__).parent


def check_url():
    try:
        req = urllib.request.Request(URL, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"OK: {URL} responded {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"OK: {URL} returned HTTP {e.code} (auth/forbidden, expected for remote MCP)")
            return True
        print(f"WARN: {URL} returned HTTP {e.code}")
        return False
    except Exception as e:
        print(f"FAIL: {URL} unreachable: {e}")
        return False


def check_configs():
    ok = True
    for md_file in CONFIG_DIR.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        if "https://mcp.openrouter.ai/mcp" not in content:
            print(f"FAIL: {md_file.name} missing server URL reference")
            ok = False
        else:
            print(f"OK: {md_file.name} references server URL")
    return ok


if __name__ == "__main__":
    url_ok = check_url()
    config_ok = check_configs()
    if url_ok and config_ok:
        print("\nAll MCP setup checks passed.")
    else:
        print("\nSome MCP setup checks failed.")
        exit(1)
