"""Anthropic API client initialization.

Provides a factory function that returns a configured Anthropic client,
or raises a clear error when the API key is missing and Claude mode was
explicitly requested.

Graceful degradation: callers that want optional Claude support should
check `get_client(require=False)` which returns None when no key is set.
"""
from __future__ import annotations

import os

_MODEL = "claude-sonnet-4-6"


def get_client(*, require: bool = False):
    """Return an initialized Anthropic client.

    Args:
        require: When True, raise ValueError if ANTHROPIC_API_KEY is not set.
                 When False, return None if the key is absent.

    Returns:
        anthropic.Anthropic instance, or None when require=False and key absent.

    Raises:
        ValueError: When require=True and ANTHROPIC_API_KEY is not set.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        if require:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it in your environment or in a .env file to use Claude classification."
            )
        return None

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "The 'anthropic' package is required for Claude classification. "
            "Install it with: pip install anthropic"
        ) from exc

    return anthropic.Anthropic(api_key=api_key)


def get_model() -> str:
    """Return the Claude model ID used for classification."""
    return _MODEL
