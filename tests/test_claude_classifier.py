"""Tests for claude_classifier module."""
from unittest.mock import MagicMock, patch

import pytest

from inbound_inquiry_analyzer.claude_classifier import classify_with_claude
from inbound_inquiry_analyzer.normalizer import NormalizedRecord


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


def _mock_client(response_text: str):
    content_block = MagicMock()
    content_block.text = response_text
    message = MagicMock()
    message.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


CATEGORIES = [
    "Issue with login",
    "Refund request",
    "Inquiry about plan or pricing",
    "Unclear",
]


def test_classify_returns_known_category():
    client = _mock_client("Refund request")
    result = classify_with_claude(_record("I want a refund", "please refund me"), CATEGORIES, client)
    assert result == "Refund request"


def test_classify_returns_new_category_from_claude():
    client = _mock_client("Accessibility request")
    result = classify_with_claude(_record("font size", "make fonts bigger"), CATEGORIES, client)
    assert result == "Accessibility request"


def test_classify_strips_whitespace():
    client = _mock_client("  Issue with login  ")
    result = classify_with_claude(_record("cant login"), CATEGORIES, client)
    assert result == "Issue with login"


def test_classify_empty_response_returns_unclear():
    client = _mock_client("")
    result = classify_with_claude(_record("something"), CATEGORIES, client)
    assert result == "Unclear"


def test_classify_missing_subject_no_error():
    client = _mock_client("Unclear")
    result = classify_with_claude(_record(subject="", body="hello"), CATEGORIES, client)
    assert result == "Unclear"


def test_classify_sends_categories_in_prompt():
    client = _mock_client("Refund request")
    classify_with_claude(_record("refund", "give me money back"), CATEGORIES, client)
    call_args = client.messages.create.call_args
    messages = call_args[1]["messages"]
    user_content = messages[0]["content"]
    for cat in CATEGORIES:
        assert cat in user_content


def test_classify_includes_subject_in_prompt():
    client = _mock_client("Issue with login")
    classify_with_claude(_record("Login broken", "can't sign in"), CATEGORIES, client)
    call_args = client.messages.create.call_args
    messages = call_args[1]["messages"]
    user_content = messages[0]["content"]
    assert "Login broken" in user_content


def test_classify_omits_subject_line_when_empty():
    client = _mock_client("Unclear")
    classify_with_claude(_record(subject="", body="some message"), CATEGORIES, client)
    call_args = client.messages.create.call_args
    messages = call_args[1]["messages"]
    user_content = messages[0]["content"]
    assert "Subject:" not in user_content
