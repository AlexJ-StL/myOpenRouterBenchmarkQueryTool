# Model Recommendation Prompt Template

Task: Recommend a model for a task using live OpenRouter data (not stale training knowledge). The assistant should defer to `list-benchmarks`, `list-daily-model-rankings`, and `list-models` via the MCP, and compare answers using `send-message` if needed.

Reference commands:

```bash
# CLI benchmark lookup (reference only — for live data use MCP or direct API)
python benchmarks.py --task <task>
```

Prompt example for harness:

> "Recommend the best model for [coding / intelligence / agentic / summarization]. Use the live OpenRouter benchmark data (not your training memory). Consider speed, cost, and benchmark index. If comparing responses, send a test message and report the generation id and cost."

Reference: docs (`[PERSON_NAME] [PERSON_NAME]`), lines 109–130; `SKILL.md`; `tools/MCP/mcp-server.md` (tool descriptions).
