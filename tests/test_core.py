"""
test_core.py

Tests for pipeline/core.py helper logic:
  - _parse_comma_list: comma expansion, whitespace trimming, empty-item filtering
  - parse_and_expand_tasks: correct keys are expanded; others pass through unchanged
  - CLI run command: exits with code 1 when --input directory is missing
"""

import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import MOCK_CONFIG

# core.py loads config.yaml at module level; patch the resulting variable
# for tests that invoke code paths touching it.
CORE_CONFIG_PATH = "neuro_pipeline.pipeline.core.config"


def _import_helpers():
    from neuro_pipeline.pipeline.core import _parse_comma_list, parse_and_expand_tasks
    return _parse_comma_list, parse_and_expand_tasks


# ---------------------------------------------------------------------------
# _parse_comma_list
# ---------------------------------------------------------------------------

class TestParseCommaList:

    def setup_method(self):
        self.fn, _ = _import_helpers()

    def test_single_comma_separated_string(self):
        assert self.fn(["cards,kidvid"]) == ["cards", "kidvid"]

    def test_already_individual_items(self):
        assert self.fn(["cards", "kidvid"]) == ["cards", "kidvid"]

    def test_mixed_input(self):
        assert self.fn(["cards,kidvid", "rest"]) == ["cards", "kidvid", "rest"]

    def test_strips_whitespace(self):
        assert self.fn(["cards, kidvid"]) == ["cards", "kidvid"]

    def test_filters_empty_items(self):
        assert self.fn(["cards,,kidvid"]) == ["cards", "kidvid"]

    def test_empty_list(self):
        assert self.fn([]) == []

    def test_single_item_no_comma(self):
        assert self.fn(["recon"]) == ["recon"]


# ---------------------------------------------------------------------------
# parse_and_expand_tasks
# ---------------------------------------------------------------------------

class TestParseAndExpandTasks:

    def setup_method(self):
        _, self.fn = _import_helpers()

    def _registry(self, return_value=None):
        reg = MagicMock()
        reg.expand_tasks.return_value = return_value or []
        return reg

    def test_intermed_comma_string_expanded(self):
        reg = self._registry()
        self.fn(reg, intermed=["volume,bfc"], bids_prep=None,
                bids_post=None, staged_prep=None, staged_post=None)
        assert reg.expand_tasks.call_args.kwargs["intermed"] == ["volume", "bfc"]

    def test_bids_prep_comma_string_expanded(self):
        reg = self._registry()
        self.fn(reg, intermed=None, bids_prep=["rest,dwi"],
                bids_post=None, staged_prep=None, staged_post=None)
        assert reg.expand_tasks.call_args.kwargs["bids_prep"] == ["rest", "dwi"]

    def test_staged_prep_comma_string_expanded(self):
        reg = self._registry()
        self.fn(reg, intermed=None, bids_prep=None,
                bids_post=None, staged_prep=["cards,kidvid"], staged_post=None)
        assert reg.expand_tasks.call_args.kwargs["staged_prep"] == ["cards", "kidvid"]

    def test_none_keys_passed_through_unchanged(self):
        reg = self._registry()
        self.fn(reg, intermed=None, bids_prep=None,
                bids_post=None, staged_prep=None, staged_post=None)
        kwargs = reg.expand_tasks.call_args.kwargs
        assert kwargs["intermed"] is None
        assert kwargs["bids_prep"] is None
        assert kwargs["staged_prep"] is None

    def test_non_list_kwargs_passed_through(self):
        reg = self._registry(["unzip"])
        self.fn(reg, prep="unzip", intermed=None,
                bids_prep=None, bids_post=None, staged_prep=None, staged_post=None)
        assert reg.expand_tasks.call_args.kwargs["prep"] == "unzip"

    def test_returns_registry_result(self):
        reg = self._registry(["recon", "volume"])
        result = self.fn(reg, intermed=None, bids_prep=None,
                         bids_post=None, staged_prep=None, staged_post=None)
        assert result == ["recon", "volume"]


# ---------------------------------------------------------------------------
# CLI — run command error paths
# ---------------------------------------------------------------------------

class TestCliRunErrors:

    def test_exits_when_input_dir_missing(self, tmp_path):
        from typer.testing import CliRunner
        with patch(CORE_CONFIG_PATH, MOCK_CONFIG):
            from neuro_pipeline.pipeline.core import app
        runner = CliRunner(mix_stderr=True)
        result = runner.invoke(app, [
            "run",
            "--subjects", "001",
            "--input", str(tmp_path / "nonexistent"),
            "--output", str(tmp_path / "output"),
            "--work", str(tmp_path / "work"),
            "--project", "test_proj",
            "--session", "01",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "not found" in (result.output or "").lower()
