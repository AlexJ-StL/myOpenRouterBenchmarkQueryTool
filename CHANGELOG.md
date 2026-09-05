# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Typed `Args` dataclass replaces fragile `argparse.Namespace` construction, giving both interactive and CLI paths a single source of truth for options.
- `_namespace_to_args()` bridge preserves argparse compatibility while the rest of the codebase moves to the typed dataclass.
- Granular HTTP timeouts via `httpx.Timeout(connect=..., read=..., write=..., pool=...)` so large benchmark responses are not killed by a 30-second global budget.

### Changed
- Error handling now raises typed exceptions (`BenchmarkAuthError`, `BenchmarkRateLimitError`, `BenchmarkServerError`, `BenchmarkAPIError`, `BenchmarkNetworkError`) instead of calling `sys.exit(1)` inside library functions. `main()` is the single exit point.
- Cache eviction caps `cache/` at 200 entries (LRU by mtime) via `_evict_if_needed()` called from `write_cache()`.
- CSV export flattens all nested dicts through `_flatten_row()`, not just `pricing`. Lists are JSON-stringified so they survive the round-trip.
- Rate-limit retry uses exponential backoff (base 5 s, 2 retries, jitter) before surfacing a `BenchmarkRateLimitError`.
- `fetch_benchmarks()` accepts injectable `_sleep` and `_random` callables for deterministic testing.

### Fixed
- Interactive mode now populates `Args` directly, eliminating the old `Namespace` attribute-name drift that broke export flags.
- `AA_INDEXES` dead export removed from `benchmark_catalog.py`.
- `exports/` restored to `.gitignore` so user-generated output files are not accidentally staged.

---

## [0.1.0] - 2026-09-04

### Added
- Initial release.
- Interactive terminal menu for selecting source, benchmark, creator, and result count.
- One-liner CLI flags: `--source`, `--task`, `--benchmark`, `--arena`, `--category`, `--creator`, `--top`, `--json`, `--csv`, `--no-cache`, `--ttl`, `--interactive`.
- Per-source Rich tables: Artificial Analysis composite indexes, Design Arena ELO rankings, OpenRouter classic + search benchmarks.
- Local JSON cache keyed by SHA-256 of request params (default 1-hour TTL) to respect OpenRouter rate limits.
- JSON and CSV export; CSV flattens nested `pricing` dicts.
- Attribution panel printed from `meta.citation` on every response.
- `.env.example`, `.gitignore`, `LICENSE` (MIT), and `pyproject.toml` with `hatchling` build backend.

[Unreleased]: https://github.com/AlexJ-StL/myOpenRouterBenchmarkQueryTool/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AlexJ-StL/myOpenRouterBenchmarkQueryTool/releases/tag/v0.1.0
