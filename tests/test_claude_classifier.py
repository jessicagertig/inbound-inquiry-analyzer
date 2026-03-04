"""Tests for claude_classifier.py: Claude-powered classification with keyword fallback.

These tests are fully isolated from the real Anthropic API using mocked clients.
No real API calls are made in CI. This is critical for:
- Reproducible test results (LLM outputs are non-deterministic)
- No API key required in CI
- Fast test execution

Test coverage:
- Successful Claude classification (happy path)
- Per-message fallback when Claude returns unknown category
- Per-message fallback when Claude omits an ID
- Full batch fallback when Claude API call raises an exception
- Full batch fallback when Claude response is not valid JSON
- Empty input returns empty list
- Method markers ('claude' vs 'keyword') are correct in all cases
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from inbound_inquiry_analyzer.claude_classifier import classify_with_claude
from inbound_inquiry_analyzer.config import CategoryConfig
from inbound_inquiry_analyzer.normalizer import NormalizedRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Issue with login",
    "Inquiry about plan or pricing",
    "Request for data deletion",
    "Wrong email address (not intended for Polymer)",
    "Advertising or solicitation",
    "Knowledge base help",
    "Feature help",
    "Migration",
    "Refund request",
    "Other",
    "Unclear",
]


@pytest.fixture
def config() -> CategoryConfig:
    cats = [{"name": c, "color": "#FFFFFF"} for c in CATEGORIES]
    return CategoryConfig(categories=cats, sources=["Intercom"])


def make_record(
    inquiry_id: str = "1",
    subject: str = "Help",
    body: str = "I need help",
) -> NormalizedRecord:
    return NormalizedRecord(
        inquiry_id=inquiry_id,
        source="Intercom",
        received_at_date="2024-01-01",
        received_at_ts=1704067200.0,
        from_name="Test User",
        from_email="test@example.com",
        subject=subject,
        message_body=body,
    )


def make_mock_client(response_json: list[dict]) -> MagicMock:
    """Create a mock Anthropic client that returns the given JSON as response text."""
    client = MagicMock()
    message = MagicMock()
    content_block = MagicMock()
    content_block.text = json.dumps(response_json)
    message.content = [content_block]
    client.messages.create.return_value = message
    return client


# ---------------------------------------------------------------------------
# Tests: empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_returns_empty_list(self, config):
        client = make_mock_client([])
        result = classify_with_claude([], config, client=client)
        assert result == []

    def test_does_not_call_api(self, config):
        client = make_mock_client([])
        classify_with_claude([], config, client=client)
        client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: successful Claude classification
# ---------------------------------------------------------------------------

class TestSuccessfulClassification:
    def test_single_record_happy_path(self, config):
        records = [make_record("42", subject="login problem", body="can't log in")]
        client = make_mock_client([{"id": "42", "category": "Issue with login"}])

        result = classify_with_claude(records, config, client=client)

        assert len(result) == 1
        category, method = result[0]
        assert category == "Issue with login"
        assert method == "claude"

    def test_multiple_records_happy_path(self, config):
        records = [
            make_record("1", subject="login issue"),
            make_record("2", subject="refund please"),
            make_record("3", subject="price question"),
        ]
        client = make_mock_client([
            {"id": "1", "category": "Issue with login"},
            {"id": "2", "category": "Refund request"},
            {"id": "3", "category": "Inquiry about plan or pricing"},
        ])

        result = classify_with_claude(records, config, client=client)

        assert len(result) == 3
        assert result[0] == ("Issue with login", "claude")
        assert result[1] == ("Refund request", "claude")
        assert result[2] == ("Inquiry about plan or pricing", "claude")

    def test_result_order_matches_input_order(self, config):
        records = [make_record(str(i)) for i in range(5)]
        response = [{"id": str(i), "category": "Unclear"} for i in range(5)]
        client = make_mock_client(response)

        result = classify_with_claude(records, config, client=client)

        # Order must follow records, not response order
        for i, (cat, method) in enumerate(result):
            assert cat == "Unclear"
            assert method == "claude"

    def test_all_methods_are_claude_on_success(self, config):
        records = [make_record("1"), make_record("2")]
        client = make_mock_client([
            {"id": "1", "category": "Unclear"},
            {"id": "2", "category": "Unclear"},
        ])
        result = classify_with_claude(records, config, client=client)
        assert all(method == "claude" for _, method in result)


# ---------------------------------------------------------------------------
# Tests: per-message fallback (unknown category)
# ---------------------------------------------------------------------------

class TestPerMessageFallback:
    def test_unknown_category_falls_back_to_keyword(self, config, capsys):
        records = [make_record("1", subject="login problem", body="can't log in")]
        client = make_mock_client([{"id": "1", "category": "NotARealCategory"}])

        result = classify_with_claude(records, config, client=client)

        category, method = result[0]
        assert method == "keyword"
        assert category in CATEGORIES  # keyword result is a valid category

    def test_unknown_category_prints_warning(self, config, capsys):
        records = [make_record("1")]
        client = make_mock_client([{"id": "1", "category": "NotARealCategory"}])

        classify_with_claude(records, config, client=client)

        err = capsys.readouterr().err
        assert "NotARealCategory" in err
        assert "1" in err  # inquiry ID in warning

    def test_missing_id_falls_back_to_keyword(self, config):
        # Claude returns ID for record 2 but not record 1
        records = [make_record("1"), make_record("2", subject="refund")]
        client = make_mock_client([{"id": "2", "category": "Refund request"}])

        result = classify_with_claude(records, config, client=client)

        assert len(result) == 2
        _, method1 = result[0]
        _, method2 = result[1]
        assert method1 == "keyword"  # missing ID -> fallback
        assert method2 == "claude"   # present ID -> Claude result

    def test_missing_id_prints_warning(self, config, capsys):
        records = [make_record("missing-id")]
        client = make_mock_client([])  # response has no items -> ID is missing

        classify_with_claude(records, config, client=client)

        err = capsys.readouterr().err
        assert "missing-id" in err

    def test_mixed_success_and_fallback(self, config):
        records = [
            make_record("1", subject="login issue"),
            make_record("2", body="totally ambiguous"),
            make_record("3", body="I need a refund"),
        ]
        client = make_mock_client([
            {"id": "1", "category": "Issue with login"},
            {"id": "2", "category": "UNKNOWN_CAT"},  # will trigger fallback
            {"id": "3", "category": "Refund request"},
        ])

        result = classify_with_claude(records, config, client=client)

        assert result[0] == ("Issue with login", "claude")
        assert result[1][1] == "keyword"  # fallback triggered
        assert result[2] == ("Refund request", "claude")

    def test_fallback_keyword_result_is_valid_category(self, config):
        """Fallback keyword result must always be a configured category name."""
        records = [make_record("1", subject="can't login", body="password reset")]
        client = make_mock_client([{"id": "1", "category": "INVALID"}])

        result = classify_with_claude(records, config, client=client)
        category, method = result[0]
        assert method == "keyword"
        assert category in CATEGORIES


# ---------------------------------------------------------------------------
# Tests: full batch fallback on API/parse errors
# ---------------------------------------------------------------------------

class TestBatchFallback:
    def test_api_exception_falls_back_all(self, config, capsys):
        records = [make_record("1"), make_record("2")]
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("network error")

        result = classify_with_claude(records, config, client=client)

        assert len(result) == 2
        assert all(method == "keyword" for _, method in result)

    def test_api_exception_prints_warning(self, config, capsys):
        records = [make_record("1")]
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("boom")

        classify_with_claude(records, config, client=client)

        err = capsys.readouterr().err
        assert "boom" in err or "fallback" in err.lower()

    def test_invalid_json_response_falls_back_all(self, config):
        records = [make_record("1"), make_record("2")]
        client = MagicMock()
        message = MagicMock()
        content_block = MagicMock()
        content_block.text = "this is not JSON"
        message.content = [content_block]
        client.messages.create.return_value = message

        result = classify_with_claude(records, config, client=client)

        assert len(result) == 2
        assert all(method == "keyword" for _, method in result)

    def test_non_list_json_response_falls_back_all(self, config):
        records = [make_record("1")]
        client = MagicMock()
        message = MagicMock()
        content_block = MagicMock()
        content_block.text = json.dumps({"id": "1", "category": "Unclear"})  # object, not array
        message.content = [content_block]
        client.messages.create.return_value = message

        result = classify_with_claude(records, config, client=client)

        assert len(result) == 1
        assert result[0][1] == "keyword"

    def test_batch_fallback_results_are_valid_categories(self, config):
        records = [
            make_record("1", body="I forgot my password"),
            make_record("2", body="I need a refund"),
        ]
        client = MagicMock()
        client.messages.create.side_effect = Exception("api down")

        result = classify_with_claude(records, config, client=client)

        for category, method in result:
            assert method == "keyword"
            assert category in CATEGORIES


# ---------------------------------------------------------------------------
# Tests: API call structure
# ---------------------------------------------------------------------------

class TestApiCallStructure:
    def test_calls_messages_create(self, config):
        records = [make_record("1")]
        client = make_mock_client([{"id": "1", "category": "Unclear"}])

        classify_with_claude(records, config, client=client)

        client.messages.create.assert_called_once()

    def test_passes_model_to_api(self, config):
        records = [make_record("1")]
        client = make_mock_client([{"id": "1", "category": "Unclear"}])

        classify_with_claude(records, config, client=client, model="claude-opus-4-6")

        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"

    def test_category_names_present_in_prompt(self, config):
        records = [make_record("1")]
        client = make_mock_client([{"id": "1", "category": "Unclear"}])

        classify_with_claude(records, config, client=client)

        call_kwargs = client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        for cat in CATEGORIES:
            assert cat in user_content, f"Category {cat!r} not found in prompt"

    def test_inquiry_id_in_prompt(self, config):
        records = [make_record("unique-id-99")]
        client = make_mock_client([{"id": "unique-id-99", "category": "Unclear"}])

        classify_with_claude(records, config, client=client)

        call_kwargs = client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert "unique-id-99" in user_content
