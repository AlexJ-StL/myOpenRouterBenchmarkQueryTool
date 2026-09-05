# Contributing

Thank you for your interest in contributing to **myOpenRouterBenchmarkQueryTool**.
This document covers the workflow, coding standards, and test requirements so that
contributions can be reviewed quickly.

---

## Code of Conduct

This project is released under the MIT license. By participating you agree to
maintain a respectful, inclusive environment. Please report unacceptable behavior
to the repository maintainer.

---

## How to Contribute

### 1. Open an Issue First

For bug reports, feature requests, or questions, open an issue before starting
work. This avoids duplicated effort and makes sure the change aligns with the
project direction.

### 2. Fork and Branch

```bash
git clone https://github.com/AlexJ-StL/myOpenRouterBenchmarkQueryTool.git
cd myOpenRouterBenchmarkQueryTool
git checkout -b my-change
```

### 3. Install Dependencies

```bash
uv sync --dev
```

### 4. Make Changes

- Keep changes focused. One topic per pull request.
- Follow the existing code style (PEP 8, type hints, `from __future__ import annotations`).
- Update `README.md` and `CHANGELOG.md` when the change is user-facing.
- Update `REMEDIATION_PLAN.md` when the change is structural or fixes a known issue.

### 5. Run Tests and Type Checks

```bash
# Tests with coverage
uv run pytest tests/ -v

# Type checking
uv run pyright benchmarks.py tests/
```

The CI runs both of these on every push. A pull request will not be merged unless
both pass.

### 6. Commit

Write a clear commit message in the imperative mood:

```
feat: add rate-limit retry with exponential backoff

HTTP 429 responses now retry twice with jitter before surfacing
a BenchmarkRateLimitError.
```

Conventional commits (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`) are
preferred but not required.

### 7. Push and Open a Pull Request

```bash
git push origin my-change
```

Open a pull request against `main`. Fill in the PR description:

- What changed and why.
- How you tested it (commands, new tests, edge cases).
- Any follow-up work or known limitations.

---

## Development Conventions

### Python Version

Target **Python 3.13+**. The project uses `from __future__ import annotations` and
the `|` union syntax.

### Imports

Standard library first, third-party second, local modules last. Blank lines between
groups. See `benchmarks.py` for the canonical pattern.

### Error Handling

Library-level functions raise typed exceptions from the `BenchmarkError` hierarchy.
`main()` is the only place that calls `sys.exit`. Never add a new `sys.exit` inside
a reusable function.

### Caching

Cache files live under `cache/` and are gitignored. The key is the first 16 hex
chars of SHA-256 over the sorted query params. Eviction is LRU by mtime, capped at
`MAX_CACHE_FILES` (currently 200).

### Tests

- Place tests in `tests/`.
- Name test classes `Test<Feature>` and test methods `test_<behavior>`.
- Use `pytest-mock` / `unittest.mock` for I/O and network boundaries.
- Use `tmp_path` for filesystem assertions; monkeypatch `benchmarks.CACHE_DIR`
  when testing cache behavior.
- Aim for meaningful coverage, not 100% for its own sake. The CI floor is 70%.

### Documentation

- Update `README.md` for user-facing changes.
- Update `CHANGELOG.md` for every release-worthy change.
- Add docstrings to public functions and classes.
- Inline comments should explain *why*, not restate the code.

---

## Questions?

Open an issue and tag it with `question`. The maintainer will respond as soon as
possible.
