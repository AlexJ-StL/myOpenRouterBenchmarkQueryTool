from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from benchmark_catalog import (
    BENCHMARK_TYPES,
    DESIGN_ARENAS,
    DESIGN_CATEGORIES,
    SOURCES,
    TASK_TYPES,
)

API_URL = "https://openrouter.ai/api/v1/benchmarks"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_TTL_SECONDS = 3600
MAX_CACHE_FILES = 200
console = Console()


class BenchmarkError(Exception):
    """Base class for recoverable benchmark query errors."""


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


def get_api_key() -> str:
    load_dotenv()
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key or key == "your-openrouter-api-key-here":
        raise BenchmarkAuthError(
            "Missing OPENROUTER_API_KEY. Set it in your environment "
            "or copy .env.example to .env and fill in your key.",
        )
    return key


def cache_key(params: dict[str, Any]) -> str:
    canonical = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def read_cache(params: dict[str, Any], ttl: int) -> dict[str, Any] | None:
    if not CACHE_DIR.exists():
        return None
    path = CACHE_DIR / f"{cache_key(params)}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - payload.get("timestamp", 0) > ttl:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    return data


def write_cache(params: dict[str, Any], data: dict[str, Any]) -> None:
    _evict_if_needed()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{cache_key(params)}.json"
    path.write_text(
        json.dumps({"timestamp": time.time(), "data": data}, default=str),
        encoding="utf-8",
    )


def _evict_if_needed() -> None:
    if not CACHE_DIR.exists():
        return
    files = sorted(
        CACHE_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    # Reserve one slot for the file about to be written.
    excess = len(files) - MAX_CACHE_FILES + 1
    if excess > 0:
        for stale in files[:excess]:
            stale.unlink()


def fetch_benchmarks(
    api_key: str,
    params: dict[str, Any],
    use_cache: bool,
    ttl: int,
) -> dict[str, Any]:
    if use_cache:
        cached = read_cache(params, ttl)
        if cached is not None:
            return cached
    headers = {"Authorization": f"Bearer {api_key}"}
    max_retries = 2
    base_delay_s = 5.0
    with httpx.Client(timeout=httpx.Timeout(
        connect=10.0,
        read=60.0,
        write=10.0,
        pool=10.0,
    )) as client:
        last_error: BenchmarkError | None = None
        for attempt in range(max_retries + 1):
            try:
                response = client.get(API_URL, headers=headers, params=params)
            except httpx.HTTPError as exc:
                last_error = BenchmarkNetworkError(f"Network error: {exc}")
                break
            if response.status_code == 429:
                if attempt < max_retries:
                    delay = base_delay_s * (2 ** attempt) + random.uniform(0, 1)
                    console.print(f"[yellow]Rate limited. Retrying in {delay:.1f}s...[/yellow]")
                    time.sleep(delay)
                    continue
                last_error = BenchmarkRateLimitError(
                    "OpenRouter allows 30 requests/min and 500 requests/day. "
                    "Wait a moment and try again, or rely on cache.",
                )
                break
            if response.status_code == 401:
                last_error = BenchmarkAuthError(
                    "Unauthorized (401). OPENROUTER_API_KEY is missing or invalid.",
                )
                break
            if response.status_code >= 500:
                last_error = BenchmarkServerError(
                    f"OpenRouter server error ({response.status_code}). Try again later.",
                )
                break
            if response.status_code != 200:
                last_error = BenchmarkAPIError(
                    f"Request failed ({response.status_code}): {response.text}",
                )
                break
            data = response.json()
            if use_cache:
                write_cache(params, data)
            return data
    if last_error is not None:
        raise last_error
    raise BenchmarkAPIError("Request failed with no response.")


def creator_of(permaslug: str | None) -> str:
    if not permaslug or "/" not in permaslug:
        return "—"
    return permaslug.split("/", 1)[0]


def parse_price(per_token_str: str | None) -> float | None:
    if not per_token_str:
        return None
    try:
        return float(per_token_str) * 1000.0
    except (TypeError, ValueError):
        return None

# The API returns pricing as cost per token; this converts to cost per 1 000 tokens
# so the rendered table columns ("$/1K in" / "$/1K out") display familiar figures.


def fmt_price(per_token_str: str | None) -> str:
    val = parse_price(per_token_str)
    if val is None:
        return "—"
    if val < 0.01:
        return f"${val:.4f}"
    return f"${val:.2f}"


def fmt_score(value: float | None, scale: float = 100.0) -> str:
    if value is None:
        return "—"
    if scale == 1.0:
        return f"{value:.3f}"
    return f"{value:.1f}"


def filter_by_creator(items: list[dict[str, Any]], creator: str | None) -> list[dict[str, Any]]:
    if not creator:
        return items
    needle = creator.lower()
    return [it for it in items if creator_of(it.get("model_permaslug")).lower() == needle]


def sort_by_score_desc(items: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    def _pick(entry: dict[str, Any]) -> float:
        val: float | None = None
        if source == "artificial-analysis":
            val = entry.get("intelligence_index")
            if val is None:
                val = entry.get("coding_index")
            if val is None:
                val = entry.get("agentic_index")
        elif source == "design-arena":
            val = entry.get("elo")
        elif source == "openrouter":
            if entry.get("benchmark_type", "").startswith("search_"):
                val = entry.get("primary_score")
            else:
                val = entry.get("accuracy")
        return val if val is not None else 0.0

    return sorted(items, key=_pick, reverse=True)


def group_by_source(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        src = item.get("source", "unknown")
        groups.setdefault(src, []).append(item)
    return groups


def render_aa_table(items: list[dict[str, Any]], top: int) -> Table:
    table = Table(title="Artificial Analysis — Composite Indexes", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Model", style="bold")
    table.add_column("Creator", style="cyan")
    table.add_column("Coding", justify="right")
    table.add_column("Intelligence", justify="right")
    table.add_column("Agentic", justify="right")
    table.add_column("$/1K in", justify="right")
    table.add_column("$/1K out", justify="right")
    for idx, it in enumerate(items[:top], start=1):
        pricing = it.get("pricing") or {}
        table.add_row(
            str(idx),
            it.get("display_name", "—"),
            creator_of(it.get("model_permaslug")),
            fmt_score(it.get("coding_index"), 100.0),
            fmt_score(it.get("intelligence_index"), 100.0),
            fmt_score(it.get("agentic_index"), 100.0),
            fmt_price(pricing.get("prompt")),
            fmt_price(pricing.get("completion")),
        )
    return table


def render_da_table(items: list[dict[str, Any]], top: int) -> Table:
    table = Table(title="Design Arena — ELO Rankings", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Model", style="bold")
    table.add_column("Creator", style="cyan")
    table.add_column("Arena", style="magenta")
    table.add_column("Category", style="magenta")
    table.add_column("ELO", justify="right", style="bold")
    table.add_column("Win%", justify="right")
    table.add_column("1/2/3/4", justify="right", style="dim")
    table.add_column("Gen ms", justify="right")
    for idx, it in enumerate(items[:top], start=1):
        stats = it.get("tournament_stats") or {}
        placements = (
            f"{stats.get('first_place') or 0}/"
            f"{stats.get('second_place') or 0}/"
            f"{stats.get('third_place') or 0}/"
            f"{stats.get('fourth_place') or 0}"
        )
        gen = it.get("avg_generation_time_ms")
        table.add_row(
            str(idx),
            it.get("display_name", "—"),
            creator_of(it.get("model_permaslug")),
            it.get("arena", "—"),
            it.get("category", "—"),
            f"{it.get('elo', 0):.0f}",
            f"{it.get('win_rate', 0):.1f}",
            placements,
            f"{gen:.0f}" if isinstance(gen, (int, float)) else "—",
        )
    return table


def render_or_table(items: list[dict[str, Any]], top: int) -> Table:
    classic = [it for it in items if not it.get("benchmark_type", "").startswith("search_")]
    search = [it for it in items if it.get("benchmark_type", "").startswith("search_")]
    if not classic and not search:
        return Table(title="OpenRouter Benchmarks")
    table = Table(title="OpenRouter Benchmarks", show_lines=False)

    if classic:
        table.add_column("#", justify="right", style="dim")
        table.add_column("Model", style="bold")
        table.add_column("Creator", style="cyan")
        table.add_column("Benchmark", style="magenta")
        table.add_column("Accuracy", justify="right", style="bold")
        table.add_column("±Std", justify="right")
        table.add_column("$/task", justify="right")
        table.add_column("Tasks", justify="right")
        table.add_column("Last Run", style="dim")
        for idx, it in enumerate(classic[:top], start=1):
            table.add_row(
                str(idx),
                it.get("display_name", "—"),
                creator_of(it.get("model_permaslug")),
                it.get("benchmark_type", "—"),
                fmt_score(it.get("accuracy"), 1.0),
                fmt_score(it.get("accuracy_stddev"), 1.0),
                f"${it['avg_cost_per_task']:.4f}"
                if isinstance(it.get("avg_cost_per_task"), (int, float))
                else "—",
                str(it.get("total_tasks") or "—"),
                (it.get("last_run_timestamp") or "—")[:10],
            )

    if search:
        if classic:
            table.add_section()
        table.add_column("#", justify="right", style="dim")
        table.add_column("Model", style="bold")
        table.add_column("Creator", style="cyan")
        table.add_column("Benchmark", style="magenta")
        table.add_column("Score", justify="right", style="bold")
        table.add_column("Metric", style="dim")
        table.add_column("$/task", justify="right")
        table.add_column("Latency ms", justify="right")
        table.add_column("Engine", style="dim")
        table.add_column("Surface", style="dim")
        for idx, it in enumerate(search[:top], start=1):
            table.add_row(
                str(idx),
                it.get("display_name", "—"),
                creator_of(it.get("model_permaslug")),
                it.get("benchmark_type", "—"),
                fmt_score(it.get("primary_score"), 1.0),
                it.get("primary_metric", "—"),
                f"${it['avg_cost_per_task']:.4f}"
                if isinstance(it.get("avg_cost_per_task"), (int, float))
                else "—",
                f"{it['avg_latency_per_task_ms']:.0f}"
                if isinstance(it.get("avg_latency_per_task_ms"), (int, float))
                else "—",
                it.get("search_engine", "—"),
                it.get("search_surface", "—"),
            )

    return table


def render_results(
    data: dict[str, Any],
    creator: str | None,
    top: int,
) -> list[Table]:
    items = data.get("data") or []
    items = filter_by_creator(items, creator)
    groups = group_by_source(items)
    tables: list[Table] = []
    for source in ("artificial-analysis", "design-arena", "openrouter"):
        bucket = groups.get(source) or []
        if not bucket:
            continue
        bucket = sort_by_score_desc(bucket, source)
        if source == "artificial-analysis":
            tables.append(render_aa_table(bucket, top))
        elif source == "design-arena":
            tables.append(render_da_table(bucket, top))
        elif source == "openrouter":
            tables.append(render_or_table(bucket, top))
    return tables


def export_json(data: dict[str, Any], path: str) -> None:
    Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    console.print(f"[green]Wrote[/green] {path}")


def export_csv(data: dict[str, Any], path: str) -> None:
    items = data.get("data") or []
    if not items:
        Path(path).write_text("", encoding="utf-8")
        console.print(f"[yellow]No items to write to {path}[/yellow]")
        return

    flat_rows = [_flatten_row(it) for it in items]
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in flat_rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in flat_rows:
            writer.writerow(row)
    console.print(f"[green]Wrote[/green] {path}")


def _flatten_row(item: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in item.items():
        if isinstance(value, dict):
            for child_key, child_val in value.items():
                row[f"{key}.{child_key}"] = child_val
        else:
            row[key] = value
    return row


def print_citation(data: dict[str, Any]) -> None:
    meta = data.get("meta") or {}
    citation = meta.get("citation")
    as_of = meta.get("as_of")
    count = meta.get("model_count")
    parts: list[str] = []
    if count is not None:
        parts.append(f"{count} models")
    if as_of:
        parts.append(f"as of {as_of[:10]}")
    summary = " · ".join(parts) if parts else ""
    if citation:
        console.print(
            Panel(
                Text(citation + (f"  ({summary})" if summary else ""), style="dim"),
                border_style="dim",
                title="Attribution",
                title_align="left",
            )
        )
    elif summary:
        console.print(f"[dim]{summary}[/dim]")


def prompt_choice(question: str, options: dict[str, str], allow_blank: bool = False) -> str:
    if not options:
        console.print("[red]No options available.[/red]")
        return ""
    while True:
        console.print(question)
        for idx, (key, desc) in enumerate(options.items(), start=1):
            console.print(f"  [bold cyan]{idx}[/bold cyan]) {key} — [dim]{desc}[/dim]")
        if allow_blank:
            console.print("  [bold cyan]0[/bold cyan]) [dim](skip — no filter)[/dim]")
        raw = console.input("[bold]Select:[/bold] ").strip()
        if allow_blank and raw == "0":
            return ""
        try:
            n = int(raw)
        except ValueError:
            console.print("[red]Enter a number.[/red]")
            continue
        if 1 <= n <= len(options):
            return list(options.keys())[n - 1]
        console.print(f"[red]Pick 1–{len(options)}.[/red]")


def interactive_menu() -> Args:
    console.print(Panel.fit("[bold]OpenRouter Benchmark Query Tool[/bold]", border_style="cyan"))
    source = prompt_choice("[bold]Pick a source:[/bold]", SOURCES)
    benchmark = ""
    task = ""
    arena = ""
    category = ""
    if source == "openrouter":
        benchmark = prompt_choice("[bold]Pick a benchmark:[/bold]", BENCHMARK_TYPES)
    elif source == "design-arena":
        arena = prompt_choice("[bold]Pick an arena:[/bold]", DESIGN_ARENAS)
        category = prompt_choice("[bold]Pick a category:[/bold]", DESIGN_CATEGORIES)
    else:
        task = prompt_choice("[bold]Pick a task type:[/bold]", TASK_TYPES)

    creator_raw = console.input(
        "[bold]Filter by creator (e.g. anthropic, openai — blank for all):[/bold] ",
    ).strip()
    top_raw = console.input("[bold]Top N (default 20):[/bold] ").strip()
    try:
        top = int(top_raw) if top_raw else 20
    except ValueError:
        top = 20

    return Args(
        source=source,
        task=task,
        benchmark=benchmark,
        arena=arena,
        category=category,
        creator=creator_raw or None,
        top=top,
        json_out=None,
        csv_out=None,
        no_cache=False,
        ttl=CACHE_TTL_SECONDS,
        interactive=True,
    )


def build_params(args: Args) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if args.source and args.source != "all":
        params["source"] = args.source
    if args.task:
        params["task_type"] = args.task
    if args.benchmark:
        params["benchmark_type"] = args.benchmark
    if args.arena:
        params["arena"] = args.arena
    if args.category:
        params["category"] = args.category
    if args.top and args.top > 0:
        params["max_results"] = args.top
    return params


def _namespace_to_args(ns: argparse.Namespace) -> Args:
    return Args(
        source=getattr(ns, "source", "all"),
        task=getattr(ns, "task", ""),
        benchmark=getattr(ns, "benchmark", ""),
        arena=getattr(ns, "arena", ""),
        category=getattr(ns, "category", ""),
        creator=getattr(ns, "creator", None),
        top=getattr(ns, "top", 20),
        json_out=getattr(ns, "json_out", None),
        csv_out=getattr(ns, "csv_out", None),
        no_cache=getattr(ns, "no_cache", False),
        ttl=getattr(ns, "ttl", CACHE_TTL_SECONDS),
        interactive=getattr(ns, "interactive", False),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="benchmarks.py",
        description="Query the OpenRouter benchmark catalog from your terminal.",
    )
    parser.add_argument("--source", choices=["all", *SOURCES.keys()], help="Benchmark source")
    parser.add_argument("--task", choices=TASK_TYPES.keys(), help="Task type filter")
    parser.add_argument("--benchmark", choices=BENCHMARK_TYPES.keys(), help="Exact benchmark id")
    parser.add_argument("--arena", choices=DESIGN_ARENAS.keys(), help="Design Arena arena")
    parser.add_argument("--category", choices=DESIGN_CATEGORIES.keys(), help="Design Arena category")
    parser.add_argument("--creator", help="Filter by creator prefix (e.g. anthropic)")
    parser.add_argument("--top", type=int, default=20, help="Max rows to display (default 20)")
    parser.add_argument("--json", dest="json_out", metavar="PATH", help="Export raw JSON to PATH")
    parser.add_argument("--csv", dest="csv_out", metavar="PATH", help="Export CSV to PATH")
    parser.add_argument("--no-cache", action="store_true", help="Bypass local cache")
    parser.add_argument(
        "--ttl",
        type=int,
        default=CACHE_TTL_SECONDS,
        help=f"Cache TTL in seconds (default {CACHE_TTL_SECONDS})",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Force interactive menu even when flags are passed",
    )

    raw_argv = sys.argv[1:]
    if not raw_argv:
        args: Args = interactive_menu()
    else:
        ns = parser.parse_args(raw_argv)
        if ns.interactive:
            args = interactive_menu()
        else:
            args = _namespace_to_args(ns)

    try:
        api_key = get_api_key()
        params = build_params(args)
        data = fetch_benchmarks(
            api_key=api_key,
            params=params,
            use_cache=not args.no_cache,
            ttl=args.ttl,
        )
    except BenchmarkError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    if args.json_out:
        export_json(data, args.json_out)
    if args.csv_out:
        export_csv(data, args.csv_out)

    if args.json_out or args.csv_out:
        console.print("[dim](Exported only — no table rendered.)[/dim]")
    else:
        tables = render_results(data, creator=args.creator, top=args.top)
        if not tables:
            console.print("[yellow]No matching models.[/yellow]")
        else:
            for table in tables:
                console.print(table)
        print_citation(data)


if __name__ == "__main__":
    main()
