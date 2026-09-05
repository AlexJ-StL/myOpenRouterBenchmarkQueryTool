# Benchmark Search Prompt Template

Task: Query the OpenRouter benchmark catalog to find models suited for a specific task.

Reference command (use CLI directly or reference via harness):

```bash
python benchmarks.py --task <task> --benchmark <benchmark> --top <N>
```

Available flags (from `README.md`):
- `--source {all,artificial-analysis,design-arena,openrouter}`
- `--task {coding,intelligence,agentic,search}`
- `--benchmark <benchmark_id>` (e.g., `gpqa_diamond`, `tau_bench_verified_airline`)
- `--creator NAME`
- `--top N` (default 20)
- `--json PATH` / `--csv PATH` / `--no-cache`

Prompt example for harness:

> "Search the OpenRouter benchmark catalog for the best coding models. Use `python benchmarks.py --task coding --top 10` and summarize the top results with their scores, creators, and pricing."

Reference: `README.md`, `SKILL.md`, `benchmarks.py`.
