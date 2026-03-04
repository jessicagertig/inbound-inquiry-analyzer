"""Tests for api_client module."""
import os
import pytest

from inbound_inquiry_analyzer.api_client import get_client, get_model


def test_get_model_returns_string():
    assert isinstance(get_model(), str)
    assert "claude" in get_model()


def test_get_client_returns_none_when_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = get_client(require=False)
    assert result is None


def test_get_client_raises_when_required_and_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_client(require=True)


def test_get_client_raises_when_key_is_empty_string(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_client(require=True)


def test_get_client_returns_none_for_empty_key_not_required(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    result = get_client(require=False)
    assert result is None


def test_get_client_returns_client_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    import anthropic
    client = get_client(require=False)
    assert client is not None
    assert isinstance(client, anthropic.Anthropic)
