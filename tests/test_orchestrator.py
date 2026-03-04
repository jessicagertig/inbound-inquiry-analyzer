"""Tests for orchestrator module."""
from unittest.mock import MagicMock, patch

import pytest

from inbound_inquiry_analyzer.normalizer import NormalizedRecord
from inbound_inquiry_analyzer.orchestrator import (
    METHOD_CLAUDE,
    METHOD_KEYWORD,
    METHOD_MIXED,
    classify_all,
)


def _record(subject="", body=""):
    return NormalizedRecord(
        inquiry_id="test-001",
        source="Intercom",
        received_at_date="2024-01-01",
        received_at_ts=1700000000.0,
        from_name="Test User",
        from_email="test@example.com",
        subject=subject,
        message_body=body,
    )


CATEGORIES = [
    "Issue with login",
    "Refund request",
    "Inquiry about plan or pricing",
    "Unclear",
]


def _mock_client(side_effects=None, return_value=None):
    """Build a mock client whose classify_with_claude raises or returns as specified."""
    client = MagicMock()
    return client


# ── keyword-only mode ───────────────────────────────────────────────────────


def test_keyword_only_uses_keyword_classifier():
    records = [_record("login broken"), _record("I want a refund")]
    predictions, method = classify_all(records, CATEGORIES, client=None, keyword_only=True)
    assert method == METHOD_KEYWORD
    assert len(predictions) == 2


def test_no_client_uses_keyword_classifier():
    records = [_record("login broken")]
    predictions, method = classify_all(records, CATEGORIES, client=None)
    assert method == METHOD_KEYWORD


def test_keyword_only_flag_ignores_client():
    fake_client = MagicMock()
    records = [_record("refund please")]
    predictions, method = classify_all(records, CATEGORIES, client=fake_client, keyword_only=True)
    # Client.messages.create should never be called
    fake_client.messages.create.assert_not_called()
    assert method == METHOD_KEYWORD


# ── Claude mode ─────────────────────────────────────────────────────────────


def test_all_claude_success_reports_claude_method():
    content_block = MagicMock()
    content_block.text = "Refund request"
    msg = MagicMock()
    msg.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = msg

    records = [_record("refund", "give me money back")]
    predictions, method = classify_all(records, CATEGORIES, client=client)
    assert method == METHOD_CLAUDE
    assert predictions == ["Refund request"]


def test_all_claude_failures_reports_keyword_method():
    client = MagicMock()
    client.messages.create.side_effect = Exception("API error")

    records = [_record("login broken"), _record("wrong address")]
    predictions, method = classify_all(records, CATEGORIES, client=client)
    assert method == METHOD_KEYWORD
    assert len(predictions) == 2


def test_partial_claude_failure_reports_mixed_method():
    # First call succeeds, second fails
    content_block = MagicMock()
    content_block.text = "Refund request"
    msg = MagicMock()
    msg.content = [content_block]
    client = MagicMock()
    client.messages.create.side_effect = [msg, Exception("rate limit")]

    records = [_record("refund"), _record("login problem")]
    predictions, method = classify_all(records, CATEGORIES, client=client)
    assert method == METHOD_MIXED
    assert predictions[0] == "Refund request"
    # Second falls back to keyword classifier
    assert isinstance(predictions[1], str)


def test_per_message_fallback_keeps_successful_results():
    content_block = MagicMock()
    content_block.text = "Refund request"
    msg = MagicMock()
    msg.content = [content_block]
    client = MagicMock()
    # Message 0: success, Message 1: failure, Message 2: success
    client.messages.create.side_effect = [msg, Exception("error"), msg]

    records = [_record("refund"), _record("login"), _record("refund again")]
    predictions, method = classify_all(records, CATEGORIES, client=client)
    assert method == METHOD_MIXED
    assert predictions[0] == "Refund request"
    assert predictions[2] == "Refund request"


def test_empty_records_returns_empty_predictions():
    predictions, method = classify_all([], CATEGORIES, client=None)
    assert predictions == []
    assert method == METHOD_KEYWORD
