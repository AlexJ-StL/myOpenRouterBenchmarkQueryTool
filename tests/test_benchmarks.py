from __future__ import annotations

import argparse
import csv
import json
import httpx
from unittest.mock import MagicMock, patch

import pytest

import benchmarks
from benchmarks import (
    Args,
    BenchmarkAPIError,
    BenchmarkAuthError,
    BenchmarkError,
    BenchmarkNetworkError,
    BenchmarkRateLimitError,
    BenchmarkServerError,
    build_params,
    cache_key,
    creator_of,
    export_csv,
    export_json,
    filter_by_creator,
    fmt_price,
    fmt_score,
    group_by_source,
    interactive_menu,
    main,
    parse_price,
    prompt_choice,
    read_cache,
    sort_by_score_desc,
    write_cache,
    _namespace_to_args,
    fetch_benchmarks,
)


# ---------------------------------------------------------------------------
# cache_key
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_deterministic(self):
        assert cache_key({"a": 1}) == cache_key({"a": 1})

    def test_different_params_different_keys(self):
        assert cache_key({"a": 1}) != cache_key({"a": 2})

    def test_order_independent(self):
        assert cache_key({"a": 1, "b": 2}) == cache_key({"b": 2, "a": 1})


# ---------------------------------------------------------------------------
# parse_price / fmt_price
# ---------------------------------------------------------------------------

class TestParsePrice:
    def test_normal(self):
        assert parse_price("0.001") == pytest.approx(1.0)

    def test_none(self):
        assert parse_price(None) is None

    def test_empty_string(self):
        assert parse_price("") is None

    def test_malformed(self):
        assert parse_price("abc") is None


class TestFmtPrice:
    def test_under_one_cent(self):
        assert fmt_price("0.0004") == "$0.40"

    def test_over_one_cent(self):
        assert fmt_price("0.01") == "$10.00"

    def test_none(self):
        assert fmt_price(None) == "—"

    def test_empty(self):
        assert fmt_price("") == "—"


# ---------------------------------------------------------------------------
# fmt_score
# ---------------------------------------------------------------------------

class TestFmtScore:
    def test_none(self):
        assert fmt_score(None) == "—"

    def test_scale_100(self):
        assert fmt_score(72.1) == "72.1"

    def test_scale_1(self):
        assert fmt_score(0.85, scale=1.0) == "0.850"


# ---------------------------------------------------------------------------
# creator_of
# ---------------------------------------------------------------------------

class TestCreatorOf:
    def test_normal_slug(self):
        assert creator_of("anthropic/claude-3") == "anthropic"

    def test_none(self):
        assert creator_of(None) == "—"

    def test_no_slash(self):
        assert creator_of("unknown-model") == "—"

    def test_empty_string(self):
        assert creator_of("") == "—"


# ---------------------------------------------------------------------------
# filter_by_creator
# ---------------------------------------------------------------------------

class TestFilterByCreator:
    def test_none_returns_all(self):
        items = [{"model_permaslug": "anthropic/claude"}, {"model_permaslug": "openai/gpt"}]
        assert filter_by_creator(items, None) == items

    def test_case_insensitive_match(self):
        items = [{"model_permaslug": "anthropic/claude"}]
        assert filter_by_creator(items, "Anthropic") == items

    def test_no_match(self):
        items = [{"model_permaslug": "openai/gpt"}]
        assert filter_by_creator(items, "anthropic") == []


# ---------------------------------------------------------------------------
# sort_by_score_desc
# ---------------------------------------------------------------------------

class TestSortByScoreDesc:
    def test_aa_fallback_order(self):
        items = [
            {"intelligence_index": None, "coding_index": 80.0, "agentic_index": 50.0},
            {"intelligence_index": 90.0, "coding_index": 70.0, "agentic_index": 40.0},
            {"intelligence_index": None, "coding_index": None, "agentic_index": 60.0},
        ]
        result = sort_by_score_desc(items, "artificial-analysis")
        assert result[0]["intelligence_index"] == 90.0
        assert result[1]["coding_index"] == 80.0
        assert result[2]["agentic_index"] == 60.0

    def test_zero_not_treated_as_missing(self):
        items = [
            {"intelligence_index": 0.0, "coding_index": 50.0},
            {"intelligence_index": None, "coding_index": 50.0},
        ]
        result = sort_by_score_desc(items, "artificial-analysis")
        assert result[0]["intelligence_index"] is None
        assert result[1]["intelligence_index"] == 0.0

    def test_design_arena_elo(self):
        items = [{"elo": 1200}, {"elo": 900}]
        result = sort_by_score_desc(items, "design-arena")
        assert result[0]["elo"] == 1200

    def test_openrouter_search(self):
        items = [
            {"benchmark_type": "search_browsecomp", "primary_score": 0.7},
            {"benchmark_type": "gpqa_diamond", "accuracy": 0.6},
        ]
        result = sort_by_score_desc(items, "openrouter")
        assert result[0]["benchmark_type"] == "search_browsecomp"


# ---------------------------------------------------------------------------
# group_by_source
# ---------------------------------------------------------------------------

class TestGroupBySource:
    def test_unknown_source_bucketed(self):
        items = [{"source": None}]
        result = group_by_source(items)
        assert None in result

    def test_mixed_sources(self):
        items = [
            {"source": "aa"},
            {"source": "or"},
            {"source": "aa"},
        ]
        result = group_by_source(items)
        assert len(result["aa"]) == 2
        assert len(result["or"]) == 1


# ---------------------------------------------------------------------------
# build_params
# ---------------------------------------------------------------------------

class TestBuildParams:
    def test_all_set(self):
        args = Args(source="openrouter", task="coding", benchmark="gpqa_diamond", top=10)
        params = build_params(args)
        assert params["source"] == "openrouter"
        assert params["task_type"] == "coding"
        assert params["benchmark_type"] == "gpqa_diamond"
        assert params["max_results"] == 10

    def test_source_all_omitted(self):
        args = Args(source="all")
        params = build_params(args)
        assert "source" not in params

    def test_top_zero_omitted(self):
        args = Args(top=0)
        params = build_params(args)
        assert "max_results" not in params

    def test_defaults_empty(self):
        args = Args()
        params = build_params(args)
        assert params == {"max_results": 20}


# ---------------------------------------------------------------------------
# read_cache / write_cache round-trip
# ---------------------------------------------------------------------------

class TestCacheRoundTrip:
    def test_write_and_read(self, tmp_path):
        original_dir = benchmarks.CACHE_DIR
        benchmarks.CACHE_DIR = tmp_path
        try:
            payload = {"source": "test", "data": [{"id": 1}]}
            write_cache({"key": "val"}, payload)
            result = read_cache({"key": "val"}, ttl=3600)
            assert result == payload
        finally:
            benchmarks.CACHE_DIR = original_dir

    def test_missing_file_returns_none(self, tmp_path):
        original_dir = benchmarks.CACHE_DIR
        benchmarks.CACHE_DIR = tmp_path
        try:
            assert read_cache({"missing": True}, ttl=3600) is None
        finally:
            benchmarks.CACHE_DIR = original_dir

    def test_expired_returns_none(self, tmp_path):
        original_dir = benchmarks.CACHE_DIR
        benchmarks.CACHE_DIR = tmp_path
        try:
            write_cache({"key": "val"}, {"data": "stale"})
            result = read_cache({"key": "val"}, ttl=-1)
            assert result is None
        finally:
            benchmarks.CACHE_DIR = original_dir

    def test_corrupt_json_returns_none(self, tmp_path):
        original_dir = benchmarks.CACHE_DIR
        benchmarks.CACHE_DIR = tmp_path
        try:
            cache_file = tmp_path / "abc123.json"
            cache_file.write_text("not-json", encoding="utf-8")
            assert read_cache({"key": "abc123"}, ttl=3600) is None
        finally:
            benchmarks.CACHE_DIR = original_dir

    def test_missing_data_key_returns_none(self, tmp_path):
        original_dir = benchmarks.CACHE_DIR
        benchmarks.CACHE_DIR = tmp_path
        try:
            cache_file = tmp_path / "bad.json"
            cache_file.write_text(json.dumps({"timestamp": 0, "oops": True}), encoding="utf-8")
            assert read_cache({"key": "bad"}, ttl=3600) is None
        finally:
            benchmarks.CACHE_DIR = original_dir


# ---------------------------------------------------------------------------
# export_json / export_csv
# ---------------------------------------------------------------------------

class TestExportJson:
    def test_writes_file(self, tmp_path):
        data = {"data": [{"id": 1}], "meta": {}}
        dest = tmp_path / "out.json"
        export_json(data, str(dest))
        assert dest.exists()
        assert json.loads(dest.read_text()) == data


class TestExportCsv:
    def test_writes_flat_rows(self, tmp_path):
        data = {"data": [
            {"name": "a", "value": 1, "pricing": {"prompt": "0.001"}},
            {"name": "b", "value": 2},
        ]}
        dest = tmp_path / "out.csv"
        export_csv(data, str(dest))
        assert dest.exists()
        rows = list(csv.DictReader(dest.open()))
        assert len(rows) == 2
        assert rows[0]["name"] == "a"
        assert rows[0]["pricing.prompt"] == "0.001"
        assert rows[1]["pricing.prompt"] == ""

    def test_empty_data_writes_empty_file(self, tmp_path):
        dest = tmp_path / "empty.csv"
        export_json({"data": []}, str(dest.with_suffix(".json")))
        export_csv({"data": []}, str(dest))
        assert dest.read_text() == ""


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    def test_all_subclasses_of_benchmark_error(self):
        for cls in (
            BenchmarkAuthError,
            BenchmarkRateLimitError,
            BenchmarkServerError,
            BenchmarkAPIError,
            BenchmarkNetworkError,
        ):
            assert issubclass(cls, BenchmarkError)

    def test_catch_base_catches_subclass(self):
        with pytest.raises(BenchmarkError):
            raise BenchmarkAuthError("test")

    def test_subclass_catch(self):
        with pytest.raises(BenchmarkRateLimitError):
            raise BenchmarkRateLimitError("429")


# ---------------------------------------------------------------------------
# _namespace_to_args
# ---------------------------------------------------------------------------

class TestNamespaceToArgs:
    def test_full_conversion(self):
        ns = argparse.Namespace(
            source="openrouter",
            task="coding",
            benchmark="gpqa",
            arena="models",
            category="code",
            creator="anthropic",
            top=10,
            json_out="out.json",
            csv_out="out.csv",
            no_cache=True,
            ttl=1800,
            interactive=False,
        )
        args = _namespace_to_args(ns)
        assert args.source == "openrouter"
        assert args.task == "coding"
        assert args.benchmark == "gpqa"
        assert args.creator == "anthropic"
        assert args.top == 10
        assert args.json_out == "out.json"
        assert args.csv_out == "out.csv"
        assert args.no_cache is True
        assert args.ttl == 1800
        assert args.interactive is False

    def test_missing_attributes_use_defaults(self):
        ns = argparse.Namespace()
        args = _namespace_to_args(ns)
        assert args.source == "all"
        assert args.top == 20
        assert args.json_out is None
        assert args.no_cache is False


# ---------------------------------------------------------------------------
# Args dataclass defaults
# ---------------------------------------------------------------------------

class TestArgsDefaults:
    def test_defaults(self):
        args = Args()
        assert args.source == "all"
        assert args.top == 20
        assert args.json_out is None
        assert args.csv_out is None
        assert args.no_cache is False
        assert args.ttl == benchmarks.CACHE_TTL_SECONDS
        assert args.interactive is False


# ---------------------------------------------------------------------------
# prompt_choice
# ---------------------------------------------------------------------------

class TestPromptChoice:
    def test_empty_options_returns_empty(self):
        with patch.object(benchmarks.console, "print") as mock_print:
            result = prompt_choice("Pick:", {})
            assert result == ""
            mock_print.assert_called()

    def test_valid_selection_returns_key(self):
        options = {"alpha": "first", "beta": "second"}
        with patch.object(benchmarks.console, "input", return_value="1"):
            result = prompt_choice("Pick:", options)
            assert result == "alpha"

    def test_invalid_then_valid_returns_first_key(self):
        options = {"alpha": "first"}
        with patch.object(benchmarks.console, "input", side_effect=["99", "1"]):
            result = prompt_choice("Pick:", options)
            assert result == "alpha"

    def test_blank_allowed_returns_empty(self):
        options = {"alpha": "first"}
        with patch.object(benchmarks.console, "input", return_value="0"):
            result = prompt_choice("Pick:", options, allow_blank=True)
            assert result == ""


# ---------------------------------------------------------------------------
# interactive_menu
# ---------------------------------------------------------------------------

class TestInteractiveMenu:
    def test_returns_args_matching_selections(self):
        with patch.object(
            benchmarks, "prompt_choice",
            side_effect=["design-arena", "models", "codecategories"],
        ), patch.object(
            benchmarks.console, "input", side_effect=["anthropic", "5"]
        ):
            args = interactive_menu()
            assert isinstance(args, Args)
            assert args.source == "design-arena"
            assert args.arena == "models"
            assert args.category == "codecategories"
            assert args.creator == "anthropic"
            assert args.top == 5
            assert args.json_out is None
            assert args.csv_out is None
            assert args.interactive is True


# ---------------------------------------------------------------------------
# main() — error handling and output routing
# ---------------------------------------------------------------------------

class TestMain:
    def test_auth_error_exits_with_code_1(self):
        with patch.object(
            benchmarks.sys, "argv", ["benchmarks.py", "--source", "openrouter"]
        ), patch.object(
            benchmarks, "get_api_key",
            side_effect=BenchmarkAuthError("bad key"),
        ), patch.object(benchmarks.console, "print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            mock_print.assert_called()

    def test_rate_limit_error_exits_with_code_1(self):
        with patch.object(
            benchmarks.sys, "argv", ["benchmarks.py", "--source", "openrouter"]
        ), patch.object(
            benchmarks, "get_api_key", return_value="fake-key"
        ), patch.object(
            benchmarks, "build_params", return_value={}
        ), patch.object(
            benchmarks, "fetch_benchmarks",
            side_effect=BenchmarkRateLimitError("429"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_success_renders_tables_and_citation(self):
        sample_data = {"data": [{"display_name": "M1"}], "meta": {"citation": "src"}}
        mock_table = MagicMock()
        with patch.object(
            benchmarks.sys, "argv", ["benchmarks.py", "--source", "openrouter", "--top", "3"]
        ), patch.object(benchmarks, "get_api_key", return_value="fake-key"), \
             patch.object(benchmarks, "build_params", return_value={"source": "openrouter"}), \
             patch.object(
                benchmarks, "fetch_benchmarks", return_value=sample_data
            ) as mock_fetch, \
             patch.object(
                benchmarks, "render_results", return_value=[mock_table]
            ) as mock_render, \
             patch.object(benchmarks, "print_citation") as mock_cite, \
             patch.object(benchmarks.console, "print") as mock_print:
            main()
            mock_fetch.assert_called_once()
            mock_render.assert_called_once_with(
                sample_data, creator=None, top=3
            )
            mock_cite.assert_called_once_with(sample_data)
            mock_print.assert_any_call(mock_table)

    def test_json_export_skips_table_render(self):
        sample_data = {"data": [], "meta": {}}
        with patch.object(
            benchmarks.sys, "argv", ["benchmarks.py", "--json", "out.json"]
        ), patch.object(benchmarks, "get_api_key", return_value="fake-key"), \
             patch.object(benchmarks, "build_params", return_value={}), \
             patch.object(
                benchmarks, "fetch_benchmarks", return_value=sample_data
            ), \
             patch.object(benchmarks, "export_json") as mock_export, \
             patch.object(benchmarks.console, "print") as mock_print, \
             patch.object(benchmarks, "render_results") as mock_render, \
             patch.object(benchmarks, "print_citation") as mock_cite:
            main()
            mock_export.assert_called_once_with(sample_data, "out.json")
            mock_render.assert_not_called()
            mock_cite.assert_not_called()
            mock_print.assert_any_call(
                "[dim](Exported only — no table rendered.)[/dim]"
            )


# ---------------------------------------------------------------------------
# fetch_benchmarks — retry behaviour
# ---------------------------------------------------------------------------

class TestFetchBenchmarksRetry:
    def test_retries_on_429_then_succeeds(self):
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": [{"id": 1}]}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = [mock_429, mock_200]

        with patch.object(benchmarks, "read_cache", return_value=None), \
             patch("httpx.Client", return_value=mock_client), \
             patch.object(benchmarks.console, "print") as mock_print, \
             patch.object(benchmarks, "write_cache"):
            result = fetch_benchmarks(
                "fake-key", {}, use_cache=False, ttl=3600
            )
            assert result == {"data": [{"id": 1}]}
            assert mock_client.get.call_count == 2
            retry_messages = [
                c for c in mock_print.call_args_list
                if "Rate limited" in str(c)
            ]
            assert len(retry_messages) == 1

    def test_exhausts_retries_on_429(self):
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_429

        with patch.object(benchmarks, "read_cache", return_value=None), \
             patch("httpx.Client", return_value=mock_client), \
             patch.object(benchmarks, "write_cache"):
            with pytest.raises(BenchmarkRateLimitError):
                fetch_benchmarks(
                    "fake-key", {}, use_cache=False, ttl=3600
                )
            assert mock_client.get.call_count == 3  # initial + 2 retries

    def test_no_retry_on_401(self):
        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_401

        with patch.object(benchmarks, "read_cache", return_value=None), \
             patch("httpx.Client", return_value=mock_client), \
             patch.object(benchmarks, "write_cache"):
            with pytest.raises(BenchmarkAuthError):
                fetch_benchmarks(
                    "fake-key", {}, use_cache=False, ttl=3600
                )
            assert mock_client.get.call_count == 1

    def test_no_retry_on_network_error(self):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.NetworkError("connection failed")

        with patch.object(benchmarks, "read_cache", return_value=None), \
             patch("httpx.Client", return_value=mock_client), \
             patch.object(benchmarks, "write_cache"):
            with pytest.raises(BenchmarkNetworkError):
                fetch_benchmarks(
                    "fake-key", {}, use_cache=False, ttl=3600
                )
            assert mock_client.get.call_count == 1

    def test_no_retry_on_200(self):
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": []}
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_200

        with patch.object(benchmarks, "read_cache", return_value=None), \
             patch("httpx.Client", return_value=mock_client), \
             patch.object(benchmarks, "write_cache"):
            result = fetch_benchmarks(
                "fake-key", {}, use_cache=False, ttl=3600
            )
            assert result == {"data": []}
            assert mock_client.get.call_count == 1


# ---------------------------------------------------------------------------
# cache eviction
# ---------------------------------------------------------------------------

class TestCacheEviction:
    def test_eviction_caps_file_count(self, tmp_path):
        original_dir = benchmarks.CACHE_DIR
        benchmarks.CACHE_DIR = tmp_path
        try:
            for i in range(benchmarks.MAX_CACHE_FILES + 5):
                write_cache({"i": i}, {"data": i})

            files = list(tmp_path.glob("*.json"))
            assert len(files) == benchmarks.MAX_CACHE_FILES
        finally:
            benchmarks.CACHE_DIR = original_dir
