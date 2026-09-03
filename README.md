# myOpenRouterBenchmarkQueryTool

A small, simple CLI to query the [OpenRouter benchmark catalog](https://openrouter.ai/api/v1/benchmarks) and find models suited for a specific task. No web UI, no database — just a numbered menu (or one-line flags) and a clean terminal table.

## Why

When you want to pick a model for something, OpenRouter's unified `/v1/benchmarks` endpoint already aggregates scores from Artificial Analysis, Design Arena, and OpenRouter's own evals (GPQA, tau-bench, and the search benchmarks). This tool gives you a fast, organized way to query it without remembering the API shape, without memorising which benchmark id means what, and without copy-pasting `curl` every time.

## Features

- **Interactive menu** — pick a source, pick a benchmark, get a sorted table. No memorisation.
- **Power-user flags** — `--task coding --creator anthropic --top 10` for one-liners.
- **Variety of model creators** — every row is grouped by `creator` (e.g. `anthropic`, `openai`, `google`, `meta-llama`) parsed from the `model_permaslug` field.
- **Local cache** — repeat queries hit a JSON cache (default 1h TTL) to stay under OpenRouter's 30 req/min · 500 req/day rate limit.
- **Cache eviction** — LRU-based eviction caps the `cache/` folder at 200 entries so disk usage stays bounded.
- **Exports** — `--json out.json` and `--csv out.csv` for piping into other tools.
- **Attribution** — the citation returned by the API is printed under every results table.
- **Rate-limit retry** — automatic exponential backoff on HTTP 429 responses (up to 2 retries).

## Prerequisites

- **Python 3.13+**
- [**uv**](https://docs.astral.sh/uv/) — fast Python package manager
- An **OpenRouter API key** — get one at <https://openrouter.ai/keys>

## Install

```bash
git clone https://github.com/AlexJ-StL/myOpenRouterBenchmarkQueryTool.git
cd myOpenRouterBenchmarkQueryTool
uv sync
```

## Configure your API key

Either export it as an environment variable (recommended):

```bash
# Windows (PowerShell)
$env:OPENROUTER_API_KEY = "sk-or-v1-..."

# macOS / Linux
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Or copy the template and edit the result:

```bash
cp .env.example .env
# then edit .env and paste your key
```

`.env` is in `.gitignore` and is **never** committed.

## Usage

### Interactive mode (no arguments)

```bash
uv run benchmarks.py
```

You will be guided through a numbered menu:

```
╭─ OpenRouter Benchmark Query Tool ────────────────╮
Pick a source:
  1) artificial-analysis — Composite indexes from Artificial Analysis (aggregated)
  2) design-arena        — Head-to-head ELO from Design Arena battles
  3) openrouter          — OpenRouter's own evals (GPQA, tau-bench, search benchmarks)
Pick a benchmark:
  1) gpqa_diamond              — Graduate-level science and reasoning Q&A (accuracy, 0-1)
  2) tau_bench_verified_airline — Agentic tool-use on airline customer service (accuracy, 0-1)
  ...
Filter by creator (e.g. anthropic, openai — blank for all):
Top N (default 20):
```

### CLI flags (one-liners)

```bash
# Top 20 across all sources for the "coding" task type
uv run benchmarks.py --task coding

# Just the GPQA Diamond benchmark, top 10
uv run benchmarks.py --benchmark gpqa_diamond --top 10

# Design Arena, models arena, codecategories, only Anthropic
uv run benchmarks.py --source design-arena --arena models --category codecategories --creator anthropic

# Search benchmarks (OpenRouter) only
uv run benchmarks.py --task search

# Export to JSON or CSV
uv run benchmarks.py --benchmark gpqa_diamond --json out.json
uv run benchmarks.py --task coding --csv coding_results.csv

# Bypass the cache
uv run benchmarks.py --task coding --no-cache
```

### All flags

| Flag | Description |
|---|---|
| `--source {all,artificial-analysis,design-arena,openrouter}` | Restrict to one source |
| `--task {coding,intelligence,agentic,search}` | Filter by task type |
| `--benchmark {gpqa_diamond,tau_bench_verified_airline,search_browsecomp,search_hle,search_dsqa,search_widesearch}` | One exact OpenRouter benchmark |
| `--arena {models,builders,agents}` | Design Arena only |
| `--category {codecategories,uicomponent,gamedev,3d,dataviz,image,video,svg}` | Design Arena only |
| `--creator NAME` | Filter by creator prefix (e.g. `anthropic`, `openai`, `google`) |
| `--top N` | Max rows per source (default 20) |
| `--json PATH` | Export raw API JSON to `PATH` |
| `--csv PATH` | Export flat CSV to `PATH` |
| `--no-cache` | Bypass the local cache |
| `--ttl SECONDS` | Cache TTL (default 3600) |
| `--interactive` | Force the menu even when flags are passed |
| `--help` | Show help |

## Benchmark catalog (what do these benchmarks measure?)

| ID | What it measures | Source |
|---|---|---|
| `gpqa_diamond` | Graduate-level science and reasoning Q&A. Higher is better (0–1). | OpenRouter |
| `tau_bench_verified_airline` | Agentic tool-use on airline customer-service tasks. Higher is better (0–1). | OpenRouter |
| `search_browsecomp` | Hard, multi-hop web research questions. Strict accuracy (0–1). | OpenRouter |
| `search_hle` | Humanity's Last Exam-style questions. Strict accuracy (0–1). | OpenRouter |
| `search_dsqa` | Domain-specific Q&A over documents. Strict accuracy (0–1). | OpenRouter |
| `search_widesearch` | Broad web Q&A, evaluated by item-weighted F1 (0–1). | OpenRouter |
| `coding_index` (AA) | Composite coding performance from Artificial Analysis (0–100). | Artificial Analysis |
| `intelligence_index` (AA) | Composite general intelligence (0–100). | Artificial Analysis |
| `agentic_index` (AA) | Composite agentic / tool-use score (0–100). | Artificial Analysis |
| Design Arena (ELO) | Head-to-head arena ratings in 8 categories × 3 arenas (models, builders, agents). | Design Arena |

## Example output (abbreviated)

```
                       Artificial Analysis — Composite Indexes
┌───┬──────────┬─────────┬───────┬─────────────┬─────────┬─────────┬──────────┐
│ # │ Model    │ Creator │ Coding│ Intelligence│ Agentic │ $/1K in │ $/1K out │
├───┼──────────┼─────────┼───────┼─────────────┼─────────┼─────────┼──────────┤
│ 1 │ Claude   │ anthropic│  72.1 │       75.4  │   58.3  │  $3.00  │   $15.00 │
│ 2 │ Sonnet 4 │ anthropic│  65.8 │       71.2  │   62.0  │  $0.80  │    $4.00 │
└───┴──────────┴─────────┴───────┴─────────────┴─────────┴─────────┴──────────┘
╭─ Attribution ─────────────────────────────────────────────────╮
│ Source: Artificial Analysis (artificialanalysis.ai) via       │
│ OpenRouter (openrouter.ai/rankings).  (50 models · as of 2026)│
╰───────────────────────────────────────────────────────────────╯
```

## How it works

- Calls `GET https://openrouter.ai/api/v1/benchmarks` with your `Authorization: Bearer <key>` header.
- Passes through your filters as query parameters exactly as the API defines.
- Caches the response under `cache/<sha256-of-params>.json` for 1 hour by default. When the cache exceeds 200 files, the oldest entries are evicted first (LRU).
- Renders a per-source table sorted by the primary score for that source.
- Prints the citation returned in `meta.citation` for attribution.
- Handles errors with a typed exception hierarchy (`BenchmarkAuthError`, `BenchmarkRateLimitError`, `BenchmarkServerError`, `BenchmarkAPIError`, `BenchmarkNetworkError`).
- Automatically retries rate-limited (HTTP 429) responses with exponential backoff before surfacing the error.

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run the test suite
uv run pytest tests/ -v

# Type-check with pyright
uv run pyright benchmarks.py tests/
```

## Data sources & attribution

This tool is a thin client over the OpenRouter `/v1/benchmarks` endpoint. All benchmark data comes from OpenRouter and its underlying sources (Artificial Analysis, Design Arena, and OpenRouter's own evals). The OpenRouter API license is MIT for the code and the public datasets are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — reuse is permitted, including commercially, with attribution. This tool surfaces the `meta.citation` returned by the API on every response, so you always have the correct attribution line to copy.

## License

[MIT](./LICENSE) — Copyright (c) 2026 AlexJ-StL.
