from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import httpx

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
    fetch_benchmarks,
    filter_by_creator,
    fmt_price,
    fmt_score,
    get_api_key,
    group_by_source,
    interactive_menu,
    main,
    parse_price,
    print_citation,
    prompt_choice,
    read_cache,
    render_aa_table,
    render_da_table,
    render_or_table,
    render_results,
    sort_by_score_desc,
    write_cache,
    _evict_if_needed,
    _flatten_row,
    _namespace_to_args,
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
# get_api_key
# ---------------------------------------------------------------------------

class TestGetApiKey:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(BenchmarkAuthError):
            get_api_key()

    def test_placeholder_key_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "your-openrouter-api-key-here")
        with pytest.raises(BenchmarkAuthError):
            get_api_key()

    def test_valid_key_returned(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-valid-key")
        assert get_api_key() == "sk-valid-key"


# ---------------------------------------------------------------------------
# fetch_benchmarks
# ---------------------------------------------------------------------------

class TestFetchBenchmarks:
    def test_cache_hit_returns_cached(self, tmp_path, monkeypatch):
        monkeypatch.setattr(benchmarks, "CACHE_DIR", tmp_path)
        cached = {"data": [{"id": 1}]}
        benchmarks.write_cache({"key": "val"}, cached)
        result = fetch_benchmarks(
            api_key="sk-test",
            params={"key": "val"},
            use_cache=True,
            ttl=3600,
        )
        assert result == cached

    def test_cache_miss_fetches_and_caches(self, tmp_path, monkeypatch):
        monkeypatch.setattr(benchmarks, "CACHE_DIR", tmp_path)
        response_data = {"data": [{"id": 2}]}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = response_data
            mock_client.get.return_value = mock_response

            result = fetch_benchmarks(
                api_key="sk-test",
                params={"key": "val"},
                use_cache=True,
                ttl=3600,
            )

        assert result == response_data
        cached = benchmarks.read_cache({"key": "val"}, ttl=3600)
        assert cached == response_data

    def test_200_without_cache_does_not_write(self):
        response_data = {"data": [{"id": 1}]}
        with patch("httpx.Client") as mock_client_cls, \
             patch.object(benchmarks, "write_cache") as mock_write:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = response_data
            mock_client.get.return_value = mock_response

            result = fetch_benchmarks(
                api_key="sk-test",
                params={},
                use_cache=False,
                ttl=3600,
            )

        assert result == response_data
        mock_write.assert_not_called()

    def test_500_raises_server_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.get.return_value = mock_response

            with pytest.raises(BenchmarkServerError, match="500"):
                fetch_benchmarks(
                    api_key="sk-test",
                    params={},
                    use_cache=False,
                    ttl=3600,
                )

    def test_generic_non_200_raises_api_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        with patch("httpx.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.get.return_value = mock_response

            with pytest.raises(BenchmarkAPIError, match="403"):
                fetch_benchmarks(
                    api_key="sk-test",
                    params={},
                    use_cache=False,
                    ttl=3600,
                )

    def test_injected_sleep_prevents_real_delay(self):
        mock_response = MagicMock()
        mock_response.status_code = 429
        with patch("httpx.Client") as mock_client_cls, \
             patch.object(benchmarks, "get_console"), \
             patch("benchmarks.time.sleep") as mock_sleep:
            mock_client = mock_client_cls.return_value.__enter__.return_value
            mock_client.get.return_value = mock_response

            with pytest.raises(BenchmarkRateLimitError):
                fetch_benchmarks(
                    api_key="sk-test",
                    params={},
                    use_cache=False,
                    ttl=3600,
                    _sleep=mock_sleep,
                    _random=lambda a, b: 0.5,
                )

        mock_sleep.assert_called()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMainArgv:
    def test_no_args_enters_interactive(self):
        with patch.object(benchmarks, "interactive_menu") as mock_menu, \
             patch.object(benchmarks, "get_api_key", return_value="sk-test"), \
             patch.object(benchmarks, "fetch_benchmarks", return_value={"data": []}), \
             patch.object(benchmarks, "render_results", return_value=[]), \
             patch.object(benchmarks, "print_citation"):
            mock_menu.return_value = Args()
            main(argv=[])
            mock_menu.assert_called_once()

    def test_interactive_flag_forces_menu(self):
        with patch.object(benchmarks, "interactive_menu") as mock_menu, \
             patch.object(benchmarks, "get_api_key", return_value="sk-test"), \
             patch.object(benchmarks, "fetch_benchmarks", return_value={"data": []}), \
             patch.object(benchmarks, "render_results", return_value=[]), \
             patch.object(benchmarks, "print_citation"):
            mock_menu.return_value = Args()
            main(argv=["--interactive"])
            mock_menu.assert_called_once()

    def test_json_export_only(self, tmp_path):
        out_file = tmp_path / "out.json"
        with patch.object(benchmarks, "get_api_key", return_value="sk-test"), \
             patch.object(benchmarks, "fetch_benchmarks", return_value={"data": [{"id": 1}], "meta": {}}), \
             patch.object(benchmarks, "export_json") as mock_export_json, \
             patch.object(benchmarks, "print_citation"):
            main(argv=["--json", str(out_file)])
            mock_export_json.assert_called_once_with(
                {"data": [{"id": 1}], "meta": {}}, str(out_file)
            )

    def test_csv_export_only(self, tmp_path):
        out_file = tmp_path / "out.csv"
        with patch.object(benchmarks, "get_api_key", return_value="sk-test"), \
             patch.object(benchmarks, "fetch_benchmarks", return_value={"data": [{"id": 1}], "meta": {}}), \
             patch.object(benchmarks, "export_csv") as mock_export_csv, \
             patch.object(benchmarks, "print_citation"):
            main(argv=["--csv", str(out_file)])
            mock_export_csv.assert_called_once_with(
                {"data": [{"id": 1}], "meta": {}}, str(out_file)
            )

    def test_benchmark_error_exits_with_code_1(self):
        with patch.object(benchmarks, "get_api_key", side_effect=BenchmarkAuthError("test")):
            with pytest.raises(SystemExit) as exc_info:
                main(argv=["--source", "openrouter"])
            assert exc_info.value.code == 1


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


# ---------------------------------------------------------------------------
# _flatten_row
# ---------------------------------------------------------------------------

class TestFlattenRow:
    def test_nested_dict_flattened(self):
        item = {"name": "m1", "pricing": {"prompt": "0.001", "completion": "0.002"}}
        row = _flatten_row(item)
        assert row["name"] == "m1"
        assert row["pricing.prompt"] == "0.001"
        assert row["pricing.completion"] == "0.002"

    def test_list_value_json_stringified(self):
        item = {"tags": ["a", "b", "c"], "name": "m1"}
        row = _flatten_row(item)
        assert row["tags"] == '["a", "b", "c"]'
        assert row["name"] == "m1"

    def test_empty_dict_returns_empty(self):
        assert _flatten_row({}) == {}


# ---------------------------------------------------------------------------
# render_aa_table
# ---------------------------------------------------------------------------

class TestRenderAaTable:
    def test_columns_and_row_count(self):
        items = [
            {"display_name": "M1", "model_permaslug": "anthropic/claude",
             "coding_index": 80.0, "intelligence_index": 90.0, "agentic_index": 50.0,
             "pricing": {"prompt": "0.001", "completion": "0.002"}},
            {"display_name": "M2", "model_permaslug": "openai/gpt",
             "coding_index": 70.0, "intelligence_index": 85.0, "agentic_index": 40.0,
             "pricing": {"prompt": "0.01", "completion": "0.02"}},
        ]
        table = render_aa_table(items, top=2)
        assert len(table.columns) == 8
        assert len(table.rows) == 2

    def test_top_n_slicing(self):
        items = [
            {"display_name": f"M{i}", "model_permaslug": f"creator/{i}",
             "coding_index": float(i), "intelligence_index": float(i),
             "agentic_index": float(i), "pricing": {}}
            for i in range(5)
        ]
        table = render_aa_table(items, top=3)
        assert len(table.rows) == 3
        assert table.columns[1]._cells[0] == "M0"

    def test_missing_indices_show_em_dash(self):
        items = [
            {"display_name": "M1", "model_permaslug": "c/m",
             "coding_index": None, "intelligence_index": None, "agentic_index": None,
             "pricing": {}},
        ]
        table = render_aa_table(items, top=1)
        assert len(table.rows) == 1
        assert table.columns[3]._cells[0] == "—"
        assert table.columns[4]._cells[0] == "—"
        assert table.columns[5]._cells[0] == "—"

    def test_empty_items_returns_table_with_title(self):
        table = render_aa_table([], top=20)
        assert table.title is not None
        assert len(table.rows) == 0


# ---------------------------------------------------------------------------
# render_da_table
# ---------------------------------------------------------------------------

class TestRenderDaTable:
    def test_columns_and_row_count(self):
        items = [
            {"display_name": "M1", "model_permaslug": "anthropic/claude",
             "arena": "models", "category": "code", "elo": 1200.0,
             "win_rate": 0.75, "tournament_stats": {
                 "first_place": 5, "second_place": 3,
                 "third_place": 2, "fourth_place": 1,
             }, "avg_generation_time_ms": 1500},
        ]
        table = render_da_table(items, top=1)
        assert len(table.columns) == 9
        assert len(table.rows) == 1

    def test_missing_tournament_stats_defaults_to_zero(self):
        items = [
            {"display_name": "M1", "model_permaslug": "c/m",
             "arena": "models", "category": "code", "elo": 1000.0,
             "win_rate": 0.5, "tournament_stats": None,
             "avg_generation_time_ms": None},
        ]
        table = render_da_table(items, top=1)
        placements = table.columns[7]._cells[0]
        assert placements == "0/0/0/0"
        assert table.columns[8]._cells[0] == "—"

    def test_top_n_slicing(self):
        items = [
            {"display_name": f"M{i}", "model_permaslug": f"c/{i}",
             "arena": "a", "category": "c", "elo": float(i),
             "win_rate": 0.5, "tournament_stats": {}, "avg_generation_time_ms": 100}
            for i in range(5)
        ]
        table = render_da_table(items, top=2)
        assert len(table.rows) == 2


# ---------------------------------------------------------------------------
# render_or_table
# ---------------------------------------------------------------------------

class TestRenderOrTable:
    def test_classic_only_has_classic_columns(self):
        items = [
            {"benchmark_type": "gpqa_diamond", "display_name": "M1",
             "model_permaslug": "o/g", "accuracy": 0.8,
             "accuracy_stddev": 0.05, "avg_cost_per_task": 0.05,
             "total_tasks": 100, "last_run_timestamp": "2024-01-01T00:00:00Z"},
        ]
        table = render_or_table(items, top=1)
        assert len(table.columns) == 9
        assert len(table.rows) == 1

    def test_search_only_has_search_columns(self):
        items = [
            {"benchmark_type": "search_browsecomp", "display_name": "M1",
             "model_permaslug": "o/g", "primary_score": 0.7,
             "primary_metric": "F1", "avg_cost_per_task": 0.1,
             "avg_latency_per_task_ms": 5000, "search_engine": "engine",
             "search_surface": "web"},
        ]
        table = render_or_table(items, top=1)
        assert len(table.columns) == 10
        assert len(table.rows) == 1

    def test_mixed_items_adds_section(self):
        classic = {"benchmark_type": "gpqa_diamond", "display_name": "C1",
                   "model_permaslug": "o/g", "accuracy": 0.8,
                   "accuracy_stddev": 0.05, "avg_cost_per_task": 0.05,
                   "total_tasks": 100, "last_run_timestamp": "2024-01-01T00:00:00Z"}
        search = {"benchmark_type": "search_browsecomp", "display_name": "S1",
                  "model_permaslug": "o/g", "primary_score": 0.7,
                  "primary_metric": "F1", "avg_cost_per_task": 0.1,
                  "avg_latency_per_task_ms": 5000, "search_engine": "e",
                  "search_surface": "w"}
        table = render_or_table([classic, search], top=1)
        assert len(table.rows) == 2

    def test_missing_cost_or_latency_shows_em_dash(self):
        items = [
            {"benchmark_type": "search_browsecomp", "display_name": "M1",
             "model_permaslug": "o/g", "primary_score": 0.7,
             "primary_metric": "F1", "avg_cost_per_task": None,
             "avg_latency_per_task_ms": None, "search_engine": "e",
             "search_surface": "w"},
        ]
        table = render_or_table(items, top=1)
        assert table.columns[6]._cells[0] == "—"
        assert table.columns[7]._cells[0] == "—"

    def test_empty_items_returns_title_only_table(self):
        table = render_or_table([], top=20)
        assert table.title is not None
        assert len(table.rows) == 0


# ---------------------------------------------------------------------------
# render_results
# ---------------------------------------------------------------------------

class TestRenderResults:
    def test_mixed_sources_dispatch_to_correct_renderer(self):
        data = {
            "data": [
                {"source": "artificial-analysis", "display_name": "AA1",
                 "model_permaslug": "c/m", "coding_index": 80.0,
                 "intelligence_index": 90.0, "agentic_index": 50.0,
                 "pricing": {}},
                {"source": "design-arena", "display_name": "DA1",
                 "model_permaslug": "c/m", "arena": "models",
                 "category": "code", "elo": 1200.0, "win_rate": 0.75,
                 "tournament_stats": {}, "avg_generation_time_ms": 1000},
                {"source": "openrouter", "display_name": "OR1",
                 "model_permaslug": "c/m", "benchmark_type": "gpqa_diamond",
                 "accuracy": 0.8, "accuracy_stddev": 0.05,
                 "avg_cost_per_task": 0.05, "total_tasks": 100,
                 "last_run_timestamp": "2024-01-01T00:00:00Z"},
            ]
        }
        tables = render_results(data, creator=None, top=2)
        assert len(tables) == 3
        assert tables[0].title == "Artificial Analysis — Composite Indexes"
        assert tables[1].title == "Design Arena — ELO Rankings"
        assert tables[2].title == "OpenRouter Benchmarks"

    def test_creator_filter_applied_before_grouping(self):
        data = {
            "data": [
                {"source": "artificial-analysis", "display_name": "A1",
                 "model_permaslug": "anthropic/claude", "coding_index": 80.0,
                 "intelligence_index": 90.0, "agentic_index": 50.0,
                 "pricing": {}},
                {"source": "artificial-analysis", "display_name": "A2",
                 "model_permaslug": "openai/gpt", "coding_index": 70.0,
                 "intelligence_index": 85.0, "agentic_index": 40.0,
                 "pricing": {}},
            ]
        }
        tables = render_results(data, creator="anthropic", top=2)
        assert len(tables) == 1
        assert len(tables[0].rows) == 1
        assert tables[0].columns[1]._cells[0] == "A1"

    def test_no_data_returns_empty_list(self):
        tables = render_results({"data": []}, creator=None, top=20)
        assert tables == []


# ---------------------------------------------------------------------------
# print_citation
# ---------------------------------------------------------------------------

class TestPrintCitation:
    def test_citation_with_summary(self):
        data = {"meta": {"citation": "OpenRouter", "model_count": 100, "as_of": "2024-01-01T00:00:00Z"}}
        with patch.object(benchmarks.console, "print") as mock_print:
            print_citation(data)
            mock_print.assert_called()

    def test_citation_only_no_summary(self):
        data = {"meta": {"citation": "OpenRouter"}}
        with patch.object(benchmarks.console, "print") as mock_print:
            print_citation(data)
            mock_print.assert_called()

    def test_summary_only_no_citation(self):
        data = {"meta": {"model_count": 50, "as_of": "2024-06-01T00:00:00Z"}}
        with patch.object(benchmarks.console, "print") as mock_print:
            print_citation(data)
            mock_print.assert_called()

    def test_neither_citation_nor_summary_prints_nothing(self):
        data = {"meta": {}}
        with patch.object(benchmarks.console, "print") as mock_print:
            print_citation(data)
            mock_print.assert_not_called()


# ---------------------------------------------------------------------------
# export_csv edge cases
# ---------------------------------------------------------------------------

class TestExportCsvEdgeCases:
    def test_mixed_nested_and_flat_rows(self, tmp_path):
        data = {"data": [
            {"name": "a", "value": 1, "pricing": {"prompt": "0.001"}},
            {"name": "b", "value": 2},
        ]}
        dest = tmp_path / "out.csv"
        export_csv(data, str(dest))
        rows = list(csv.DictReader(dest.open()))
        assert len(rows) == 2
        assert rows[0]["name"] == "a"
        assert rows[0]["pricing.prompt"] == "0.001"
        assert rows[1]["pricing.prompt"] == ""

    def test_unicode_and_special_characters(self, tmp_path):
        data = {"data": [
            {"name": "café", "desc": "hello\nworld", "value": 1},
        ]}
        dest = tmp_path / "out.csv"
        export_csv(data, str(dest))
        content = dest.read_text(encoding="utf-8")
        assert "café" in content

    def test_field_ordering_consistent(self, tmp_path):
        data = {"data": [
            {"z": 1, "a": 2, "m": 3},
            {"z": 4, "a": 5, "m": 6},
        ]}
        dest = tmp_path / "out.csv"
        export_csv(data, str(dest))
        rows = list(csv.DictReader(dest.open()))
        fieldnames = rows[0].keys()
        assert list(fieldnames) == ["z", "a", "m"]


# ---------------------------------------------------------------------------
# build_params edge cases
# ---------------------------------------------------------------------------

class TestBuildParamsEdgeCases:
    def test_whitespace_only_strings_are_stripped_and_omitted(self):
        args = Args(task="   ", benchmark="  ", arena="", category="\t")
        params = build_params(args)
        assert "task_type" not in params
        assert "benchmark_type" not in params
        assert "arena" not in params
        assert "category" not in params

    def test_negative_top_is_omitted(self):
        args = Args(top=-1)
        params = build_params(args)
        assert "max_results" not in params


# ---------------------------------------------------------------------------
# _namespace_to_args edge cases
# ---------------------------------------------------------------------------

class TestNamespaceToArgsEdgeCases:
    def test_extra_attributes_ignored(self):
        ns = argparse.Namespace(
            source="openrouter",
            unexpected_attr="ignored",
        )
        args = _namespace_to_args(ns)
        assert args.source == "openrouter"
        assert not hasattr(args, "unexpected_attr")

    def test_wrong_type_top_stored_as_is(self):
        ns = argparse.Namespace(top="not-an-int")
        args = _namespace_to_args(ns)
        assert args.top == "not-an-int"


# ---------------------------------------------------------------------------
# _evict_if_needed edge cases
# ---------------------------------------------------------------------------

class TestEvictIfNeededEdgeCases:
    def test_no_eviction_when_under_limit(self, tmp_path):
        original_dir = benchmarks.CACHE_DIR
        benchmarks.CACHE_DIR = tmp_path
        try:
            for i in range(10):
                write_cache({"i": i}, {"data": i})
            files = list(tmp_path.glob("*.json"))
            assert len(files) == 10
        finally:
            benchmarks.CACHE_DIR = original_dir

    def test_no_op_when_directory_missing(self):
        original_dir = benchmarks.CACHE_DIR
        benchmarks.CACHE_DIR = Path("/nonexistent/path/that/does/not/exist")
        try:
            benchmarks._evict_if_needed()
        finally:
            benchmarks.CACHE_DIR = original_dir


# ---------------------------------------------------------------------------
# benchmark_catalog.py
# ---------------------------------------------------------------------------

class TestBenchmarkCatalog:
    def test_all_expected_sources_present(self):
        assert "artificial-analysis" in benchmarks.SOURCES
        assert "design-arena" in benchmarks.SOURCES
        assert "openrouter" in benchmarks.SOURCES

    def test_all_expected_task_types_present(self):
        assert "coding" in benchmarks.TASK_TYPES
        assert "intelligence" in benchmarks.TASK_TYPES
        assert "agentic" in benchmarks.TASK_TYPES
        assert "search" in benchmarks.TASK_TYPES

    def test_all_expected_benchmark_types_present(self):
        assert "gpqa_diamond" in benchmarks.BENCHMARK_TYPES
        assert "search_browsecomp" in benchmarks.BENCHMARK_TYPES

    def test_all_values_are_non_empty_strings(self):
        for d in (benchmarks.SOURCES, benchmarks.TASK_TYPES,
                  benchmarks.BENCHMARK_TYPES, benchmarks.DESIGN_ARENAS,
                  benchmarks.DESIGN_CATEGORIES):
            for key, value in d.items():
                assert isinstance(key, str)
                assert isinstance(value, str)
                assert len(key) > 0
                assert len(value) > 0

    def test_no_duplicate_keys(self):
        for d in (benchmarks.SOURCES, benchmarks.TASK_TYPES,
                  benchmarks.BENCHMARK_TYPES, benchmarks.DESIGN_ARENAS,
                  benchmarks.DESIGN_CATEGORIES):
            assert len(d.keys()) == len(set(d.keys()))


# ---------------------------------------------------------------------------
# Args full construction
# ---------------------------------------------------------------------------

class TestArgsFullConstruction:
    def test_all_fields_non_default(self):
        args = Args(
            source="openrouter",
            task="coding",
            benchmark="gpqa_diamond",
            arena="models",
            category="codecategories",
            creator="anthropic",
            top=50,
            json_out="out.json",
            csv_out="out.csv",
            no_cache=True,
            ttl=1800,
            interactive=True,
        )
        assert args.source == "openrouter"
        assert args.task == "coding"
        assert args.top == 50
        assert args.json_out == "out.json"
        assert args.no_cache is True
        assert args.ttl == 1800
        assert args.interactive is True

    def test_creator_none_vs_empty_string(self):
        args_none = Args(creator=None)
        args_empty = Args(creator="")
        assert args_none.creator is None
        assert args_empty.creator == ""


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_end_to_end_with_mocked_api(self, tmp_path):
        sample_data = {
            "data": [
                {"source": "openrouter", "display_name": "M1",
                 "model_permaslug": "openai/gpt", "benchmark_type": "gpqa_diamond",
                 "accuracy": 0.8, "accuracy_stddev": 0.05,
                 "avg_cost_per_task": 0.05, "total_tasks": 100,
                 "last_run_timestamp": "2024-01-01T00:00:00Z"},
            ],
            "meta": {"citation": "OpenRouter", "model_count": 1, "as_of": "2024-01-01T00:00:00Z"},
        }
        out_json = tmp_path / "out.json"
        with patch.object(benchmarks, "get_api_key", return_value="sk-test"), \
             patch.object(benchmarks, "fetch_benchmarks", return_value=sample_data), \
             patch.object(benchmarks, "get_console") as mock_console:
            main(argv=["--json", str(out_json), "--source", "openrouter"])
            assert out_json.exists()
            assert json.loads(out_json.read_text()) == sample_data
