"""Tests for cli.py: argument parsing, Claude/keyword mode selection, dotenv loading.

CLI tests use tmp_path for file I/O and mock the claude_classifier to avoid
real API calls. The goal is to verify wiring logic — not re-test classification
correctness (covered in test_classifier.py and test_claude_classifier.py).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from inbound_inquiry_analyzer.cli import main


# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

_INTERCOM_RECORD = {
    "_source_type": "intercom",
    "id": "101",
    "created_at": 1704067200,
    "contact_name": "Alice",
    "contact_email": "alice@example.com",
    "subject": "Can't log in",
    "first_message": "I cannot sign in to my account.",
}


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: --keyword-only flag
# ---------------------------------------------------------------------------

class TestKeywordOnlyFlag:
    def test_keyword_only_flag_skips_claude(self, tmp_path):
        input_file = tmp_path / "input.json"
        write_json(input_file, [_INTERCOM_RECORD])
        output_file = tmp_path / "out.xlsx"

        with patch("inbound_inquiry_analyzer.cli.classify_with_claude") as mock_claude:
            # Even if we import it, it should not be called
            result = main([str(input_file), "-o", str(output_file), "--keyword-only"])

        assert result == 0
        assert output_file.exists()
        mock_claude.assert_not_called()

    def test_keyword_only_produces_valid_xlsx(self, tmp_path):
        input_file = tmp_path / "input.json"
        write_json(input_file, [_INTERCOM_RECORD])
        output_file = tmp_path / "out.xlsx"

        result = main([str(input_file), "-o", str(output_file), "--keyword-only"])

        assert result == 0
        assert output_file.exists()
        assert output_file.stat().st_size > 0


# ---------------------------------------------------------------------------
# Tests: API key absence -> keyword fallback
# ---------------------------------------------------------------------------

class TestApiKeyAbsence:
    def test_no_api_key_falls_back_to_keyword(self, tmp_path, capsys):
        input_file = tmp_path / "input.json"
        write_json(input_file, [_INTERCOM_RECORD])
        output_file = tmp_path / "out.xlsx"

        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = main([str(input_file), "-o", str(output_file)])

        assert result == 0
        err = capsys.readouterr().err
        assert "ANTHROPIC_API_KEY" in err

    def test_no_api_key_warning_to_stderr(self, tmp_path, capsys):
        input_file = tmp_path / "input.json"
        write_json(input_file, [_INTERCOM_RECORD])
        output_file = tmp_path / "out.xlsx"

        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            main([str(input_file), "-o", str(output_file)])

        err = capsys.readouterr().err
        assert "Warning" in err
        assert "ANTHROPIC_API_KEY" in err


# ---------------------------------------------------------------------------
# Tests: Claude mode (mocked)
# ---------------------------------------------------------------------------

class TestClaudeMode:
    def _make_mock_classify(self, category: str = "Issue with login"):
        """Return a mock classify_with_claude that returns fixed results."""
        def mock_classify(records, config, **kwargs):
            return [(category, "claude")] * len(records)
        return mock_classify

    def test_claude_mode_called_when_api_key_set(self, tmp_path, capsys):
        input_file = tmp_path / "input.json"
        write_json(input_file, [_INTERCOM_RECORD])
        output_file = tmp_path / "out.xlsx"

        mock_classify = self._make_mock_classify()
        env = dict(os.environ, ANTHROPIC_API_KEY="test-key")
        with patch.dict(os.environ, env):
            with patch(
                "inbound_inquiry_analyzer.cli.classify_with_claude",
                side_effect=mock_classify,
            ) as mock_fn:
                result = main([str(input_file), "-o", str(output_file)])

        assert result == 0
        mock_fn.assert_called_once()

    def test_claude_mode_produces_valid_xlsx(self, tmp_path):
        input_file = tmp_path / "input.json"
        write_json(input_file, [_INTERCOM_RECORD])
        output_file = tmp_path / "out.xlsx"

        mock_classify = self._make_mock_classify("Issue with login")
        env = dict(os.environ, ANTHROPIC_API_KEY="test-key")
        with patch.dict(os.environ, env):
            with patch("inbound_inquiry_analyzer.cli.classify_with_claude", side_effect=mock_classify):
                result = main([str(input_file), "-o", str(output_file)])

        assert result == 0
        assert output_file.exists()

    def test_method_summary_logged_to_stderr(self, tmp_path, capsys):
        input_file = tmp_path / "input.json"
        write_json(input_file, [_INTERCOM_RECORD])
        output_file = tmp_path / "out.xlsx"

        mock_classify = self._make_mock_classify("Issue with login")
        env = dict(os.environ, ANTHROPIC_API_KEY="test-key")
        with patch.dict(os.environ, env):
            with patch("inbound_inquiry_analyzer.cli.classify_with_claude", side_effect=mock_classify):
                main([str(input_file), "-o", str(output_file)])

        err = capsys.readouterr().err
        # Method summary should mention "claude"
        assert "claude" in err.lower()

    def test_mixed_methods_summary(self, tmp_path, capsys):
        records = [_INTERCOM_RECORD, dict(_INTERCOM_RECORD, id="102")]
        input_file = tmp_path / "input.json"
        write_json(input_file, records)
        output_file = tmp_path / "out.xlsx"

        # Return one claude, one keyword
        def mixed_classify(recs, config, **kwargs):
            return [("Issue with login", "claude"), ("Unclear", "keyword")]

        env = dict(os.environ, ANTHROPIC_API_KEY="test-key")
        with patch.dict(os.environ, env):
            with patch("inbound_inquiry_analyzer.cli.classify_with_claude", side_effect=mixed_classify):
                main([str(input_file), "-o", str(output_file)])

        err = capsys.readouterr().err
        assert "claude" in err.lower()
        assert "keyword" in err.lower()


# ---------------------------------------------------------------------------
# Tests: existing CLI behaviors still work
# ---------------------------------------------------------------------------

class TestExistingBehaviors:
    def test_no_input_returns_error(self, capsys):
        # Simulate no stdin (isatty=True) and no args
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = main([])
        assert result == 1

    def test_missing_file_returns_error(self, tmp_path, capsys):
        result = main([str(tmp_path / "nonexistent.json"), "--keyword-only"])
        assert result == 1

    def test_output_path_respected(self, tmp_path):
        input_file = tmp_path / "input.json"
        write_json(input_file, [_INTERCOM_RECORD])
        custom_output = tmp_path / "custom_name.xlsx"

        result = main([str(input_file), "-o", str(custom_output), "--keyword-only"])

        assert result == 0
        assert custom_output.exists()

    def test_processed_count_in_stderr(self, tmp_path, capsys):
        records = [_INTERCOM_RECORD, dict(_INTERCOM_RECORD, id="102")]
        input_file = tmp_path / "input.json"
        write_json(input_file, records)
        output_file = tmp_path / "out.xlsx"

        main([str(input_file), "-o", str(output_file), "--keyword-only"])

        err = capsys.readouterr().err
        assert "2" in err  # 2 records processed
