# Remediation Plan — myOpenRouterBenchmarkQueryTool

> Status key: 🔴 Not started · 🟡 In progress · ✅ Done
> Effort: S = trivial (< 10 min) · M = medium (10–60 min) · L = large (> 1 hr)

---

## 0. Immediate Corrections (introduced during the fix pass)

### 0-A. Restore `exports/` to `.gitignore`
**Severity:** Medium · **Effort:** S

The `.gitignore` edit that removed `*.json` also accidentally removed the `exports/` entry
and replaced it with a comment. User-generated export files (`--json out.json`,
`--csv results.csv`) will now be picked up by `git status` and are at risk of being
committed.

```diff
 # .gitignore
 cache/
-# Keep exports/ for user output
+exports/
 .DS_Store
```

---

### 0-B. Remove dead `AA_INDEXES` export from `benchmark_catalog.py`
**Severity:** Low · **Effort:** S

`AA_INDEXES` is confirmed unused — zero references anywhere in the repo after the
`benchmarks.py` import was removed. It should be deleted from `benchmark_catalog.py`
(lines 40–44) to prevent future accidental re-import.

```python
# Remove this entire block from benchmark_catalog.py:
AA_INDEXES = {
    "coding_index": "Composite coding performance (0-100, higher is better)",
    "intelligence_index": "Composite general intelligence (0-100, higher is better)",
    "agentic_index": "Composite agentic / tool-use (0-100, higher is better)",
}
```

---

## 1. Error Handling — Replace `sys.exit(1)` with Exceptions
**Severity:** Medium · **Effort:** M

**Files:** `benchmarks.py` — `get_api_key()` (lines 35–44), `fetch_benchmarks()` (lines 78–117)

**Problem:** Six `sys.exit(1)` calls inside library-level functions couple error reporting
to process termination. This makes the functions untestable without subprocess capture
and prevents any caller from recovering or transforming the error.

**Proposed change:**

```python
# benchmarks.py — add near the top, after imports
class BenchmarkError(Exception):
    """Recoverable error from the benchmark query pipeline."""


class BenchmarkAuthError(BenchmarkError):
    """OPENROUTER_API_KEY is missing or invalid."""


class BenchmarkRateLimitError(BenchmarkError):
    """OpenRouter rate limit hit (HTTP 429)."""


class BenchmarkServerError(BenchmarkError):
    """OpenRouter returned a 5xx response."""


class BenchmarkAPIError(BenchmarkError):
    """OpenRouter returned an unexpected non-200 response."""


class BenchmarkNetworkError(BenchmarkError):
    """Network-level failure reaching the API."""
```

Replace each `sys.exit(1)` in `fetch_benchmarks` and `get_api_key` with the
corresponding raise:

| Current call site | Replace with |
|---|---|
| `get_api_key()` missing key | `raise BenchmarkAuthError(...)` |
| `fetch_benchmarks` httpx.HTTPError | `raise BenchmarkNetworkError(...)` from exc |
| 401 response | `raise BenchmarkAuthError(...)` |
| 429 response | `raise BenchmarkRateLimitError(...)` |
| ≥500 response | `raise BenchmarkServerError(...)` |
| other non-200 | `raise BenchmarkAPIError(...)` |

Add a single handler in `main()`:

```python
def main() -> None:
    ...
    try:
        data = fetch_benchmarks(...)
    except BenchmarkError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)
```

**Benefit:** All six error paths become individually testable with `pytest.raises`.
Callers that import these functions (future library use) can catch specific subtypes.

---

## 2. Add Tests
**Severity:** High · **Effort:** L

**New files:** `tests/test_benchmarks.py`, `tests/test_catalog.py`

The project has 24 functions, at least 12 of which are pure or near-pure and trivially
testable with no network or I/O:

| Function | Test focus |
|---|---|
| `cache_key` | deterministic output for same params; different params → different keys |
| `parse_price` | normal value, `None`, empty string, malformed string |
| `fmt_price` | < 0.01 → 4 decimals; ≥ 0.01 → 2 decimals; `None` → "—" |
| `fmt_score` | `None` → "—"; scale=1.0 → 3 decimals; scale=100 → 1 decimal |
| `creator_of` | `None`, no-slug, normal slug, empty string |
| `filter_by_creator` | `None` creator → identity; case-insensitive match; no-match → empty |
| `sort_by_score_desc` | AA fallback order (intel → coding → agentic); score=0 not treated as missing |
| `group_by_source` | unknown source bucket; mixed sources |
| `build_params` | each flag independently; `source="all"` omitted; `top ≤ 0` omitted |
| `read_cache` | cache hit, TTL expired, corrupt JSON, missing `data` key |
| `write_cache` + `read_cache` round-trip | write then read returns identical dict |
| `interactive_menu` | requires mocking `console.input`; verify Namespace attribute names |

`export_csv` and `export_json` should write to `tempfile` destinations and assert
file contents.

**Setup:**

```toml
# pyproject.toml — add under [project.optional-dependencies]
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pyright>=1.1",
]

# [tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=benchmarks --cov=benchmark_catalog"
```

---

## 3. Cache Eviction and Size Limit
**Severity:** Low · **Effort:** M

**File:** `benchmarks.py` — `write_cache()`, `read_cache()`

**Problem:** Every unique parameter set writes a new file with no eviction. Long-term
users exploring many filter combinations will see unbounded growth in `cache/`.

**Proposed approach — LRU count cap:**

```python
MAX_CACHE_FILES = 200   # tunable constant at module level

def _evict_if_needed() -> None:
    """Remove oldest files if cache exceeds MAX_CACHE_FILES."""
    if not CACHE_DIR.exists():
        return
    files = sorted(
        CACHE_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    excess = len(files) - MAX_CACHE_FILES
    if excess > 0:
        for stale in files[:excess]:
            stale.unlink()
```

Call `_evict_if_needed()` at the top of `write_cache()` before writing.

Alternative: size-based cap (sum of file sizes). Count-based is simpler and sufficient
for JSON metadata responses of ~100 KB each (200 files ≈ 20 MB ceiling).

---

## 4. CSV Export — Flatten All Nested Dicts
**Severity:** Low · **Effort:** M

**File:** `benchmarks.py` — `export_csv()` (lines 346–370)

**Problem:** Only `pricing` is expanded into flat columns (`pricing.prompt`,
`pricing.completion`). Other nested dicts like `tournament_stats` (Design Arena) and
`meta` are serialized as Python repr strings or dropped.

**Proposed helper:**

```python
def _flatten_row(item: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in item.items():
        if isinstance(value, dict):
            for child_key, child_val in value.items():
                row[f"{key}.{child_key}"] = child_val
        else:
            row[key] = value
    return row
```

Replace the inline field-building loop in `export_csv` with a call to `_flatten_row`,
removing the special-case `pricing` block. This generalises to any nested dict the API
returns now or in future versions.

---

## 5. Type-Checker Configuration
**Severity:** Low · **Effort:** S

**File:** `pyproject.toml`

Add `pyright` config (lighter weight than mypy for this codebase, no stubs needed):

```toml
[tool.pyright]
pythonVersion = "3.13"
reportMissingTypeStubs = false
reportUnusedVariable = true
reportUnusedImport = true
```

Or, for stricter enforcement, `mypy`:

```toml
[tool.mypy]
python_version = "3.13"
strict = true
```

Then add `pyright` (or `mypy`) to the `dev` optional-dependencies group from item 2.

**Benefit:** Would have caught the `Namespace` attribute-name drift (#17) at build time
if the interactive path used the same typed interface as the argparse path.

---

## 6. Replace `argparse.Namespace` with a Dataclass
**Severity:** Medium · **Effort:** M

**File:** `benchmarks.py` — `interactive_menu()`, `main()`, `build_params()`

**Problem:** `interactive_menu()` manually constructs `argparse.Namespace` with
hardcoded field names. This is fragile — any rename in the argparse parser or in
`build_params` silently breaks one path but not the other.

**Proposed change:**

```python
from dataclasses import dataclass

@dataclass
class Args:
    source: str = "all"
    task: str = ""
    benchmark: str = ""
    arena: str = ""
    category: str = ""
    creator: str | None = None
    top: int = 20
    json_out: str | None = None
    csv_out: str | None = None
    no_cache: bool = False
    ttl: int = CACHE_TTL_SECONDS
    interactive: bool = False
```

After `parser.parse_args()`, convert:

```python
ns = parser.parse_args(raw_argv)
args = Args(
    source=ns.source,
    task=ns.task,
    ...
    json_out=ns.json_out,
    ...
)
```

`interactive_menu()` returns `Args(...)` directly. `build_params` and `main()` both
receive a typed `Args` — static analysers can verify field consistency.

**Note:** This is a structural improvement. The current `Namespace` fix (#17) has
already eliminated the runtime crash; this item prevents regression.

---

## 7. Rate-Limit Retry with Exponential Backoff
**Severity:** Low · **Effort:** M

**File:** `benchmarks.py` — `fetch_benchmarks()`

**Problem:** A 429 response exits immediately. The user's own cache may have a fresh
copy, but the tool doesn't fall back to it, nor does it retry.

**Proposed change:**

```python
import random

MAX_RETRIES = 2
BASE_DELAY_S = 5

def fetch_benchmarks(..., retries: int = MAX_RETRIES) -> dict[str, Any]:
    ...
    for attempt in range(retries + 1):
        ...
        if response.status_code == 429:
            if attempt < retries:
                delay = BASE_DELAY_S * (2 ** attempt) + random.uniform(0, 1)
                console.print(f"[yellow]Rate limited. Retrying in {delay:.1f}s...[/yellow]")
                time.sleep(delay)
                continue
            raise BenchmarkRateLimitError(...)
        ...
```

This keeps the CLI responsive without silently swallowing errors. The cache-first
behaviour already in `fetch_benchmarks` (check cache before network) provides the
fast path.

---

## 8. HTTP Timeout Granularity
**Severity:** Low · **Effort:** S

**File:** `benchmarks.py` — `fetch_benchmarks()` line 86

Current:
```python
httpx.Client(timeout=30.0)
```

Change to:
```python
httpx.Client(timeout=httpx.Timeout(
    connect=10.0,
    read=60.0,
    write=10.0,
    pool=10.0,
))
```

Rationale: benchmark responses can be large (many model entries); a 30-second total
budget penalises slow reads. Connect and write can stay short; read gets headroom.

---

## 9. Whitespace Cleanup in `benchmarks.py`
**Severity:** Low · **Effort:** S

The comment block added for `parse_price` (item #14) has a stray double blank line
before it (lines 133–135). Collapse to one blank line to match PEP 8 spacing around
top-level definitions.

---

## Execution Order

```
Session 1 (this session — quick wins)
  ├── 0-A  Restore exports/ to .gitignore
  ├── 0-B  Remove AA_INDEXES from benchmark_catalog.py
  ├── 9    Whitespace cleanup
  └── 5    Add pyright config to pyproject.toml + dev deps

Session 2 (next focused session — structural)
  ├── 1    sys.exit → exception hierarchy in benchmarks.py
  ├── 2    Scaffold tests/ and write pure-function test suite
  └── 6    Args dataclass + Namespace→Args conversion

Session 3 (polish)
  ├── 3    Cache eviction (_evict_if_needed)
  ├── 4    CSV flatten-all-nested-dicts
  ├── 7    Rate-limit retry/backoff
  └── 8    HTTP timeout granularity
```

Sessions 1 and 2 are independent of each other. Session 3 can run after Session 2
finishes and tests are green.
