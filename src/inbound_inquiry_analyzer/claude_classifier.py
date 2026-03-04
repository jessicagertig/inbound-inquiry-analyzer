"""Claude-powered inquiry classifier.

Classifies inbound inquiries using Claude AI (claude-sonnet-4-6 by default).

Key design decisions:
- `import anthropic` is deferred inside `create_client()` so the package can be
  imported without the `anthropic` library being installed (e.g., when running
  with `--keyword-only` mode).
- Returns `list[tuple[str, str]]` where each tuple is `(category, method)`.
  `method` is `'claude'` on success or `'keyword'` on per-message fallback.
- Per-message fallback: if Claude fails on one message, that message falls back
  to keyword classification while other messages keep their Claude results.
  This is important because batch failures for a single bad message should not
  discard valid results for the rest of the batch.
- The keyword fallback uses the same `classify()` function from `classifier.py`
  for consistency, so fallback results are always valid category names.
"""
from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING

from inbound_inquiry_analyzer.classifier import classify
from inbound_inquiry_analyzer.config import CategoryConfig
from inbound_inquiry_analyzer.normalizer import NormalizedRecord

if TYPE_CHECKING:
    import anthropic as _anthropic

# Default model to use for classification. Callers can override via `model` param.
_DEFAULT_MODEL = "claude-sonnet-4-6"

# System prompt explaining the classification task
_SYSTEM_PROMPT = """\
You are an expert customer support classifier. Your job is to classify \
inbound customer inquiries into exactly one of the provided categories.

For each inquiry, you will receive:
- An inquiry ID
- A subject line
- A message body

Respond with a JSON array where each element is an object with:
- "id": the inquiry ID (string, exactly as provided)
- "category": one of the allowed categories (string, exactly as listed)

Rules:
- You MUST use only the exact category names provided — no variations.
- Classify based on the primary intent of the inquiry.
- If the inquiry does not fit any specific category, use "Unclear".
- Return ONLY the JSON array, no explanation, no markdown code fences.\
"""


def create_client() -> "_anthropic.Anthropic":
    """Create and return an Anthropic client.

    Import is deferred to avoid ImportError when `anthropic` is not installed
    (e.g., tests that only use keyword mode, or `--keyword-only` CLI invocations).

    Returns:
        Configured Anthropic client using ANTHROPIC_API_KEY from the environment.

    Raises:
        ImportError: If the `anthropic` package is not installed.
        anthropic.AuthenticationError: If the API key is invalid.
    """
    import anthropic  # noqa: PLC0415 — deferred on purpose
    return anthropic.Anthropic()


def _build_user_message(records: list[NormalizedRecord], categories: list[str]) -> str:
    """Build the user message content for the classification request."""
    cats_list = "\n".join(f"- {c}" for c in categories)
    inquiries_parts: list[str] = []
    for rec in records:
        inquiries_parts.append(
            f"ID: {rec.inquiry_id}\n"
            f"Subject: {rec.subject}\n"
            f"Message: {rec.message_body}"
        )
    inquiries_text = "\n\n---\n\n".join(inquiries_parts)
    return (
        f"Allowed categories:\n{cats_list}\n\n"
        f"Inquiries to classify:\n\n{inquiries_text}"
    )


def _parse_claude_response(
    response_text: str,
    records: list[NormalizedRecord],
) -> dict[str, str]:
    """Parse Claude's JSON response into a {inquiry_id: category} mapping.

    Args:
        response_text: Raw text from Claude's response.
        records: Original records (used to validate IDs present in response).

    Returns:
        Dict mapping inquiry_id to category string.

    Raises:
        ValueError: If the response is not valid JSON, not a list, or missing IDs.
    """
    try:
        data = json.loads(response_text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude response is not valid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Claude response must be a JSON array, got {type(data).__name__}")

    result: dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"Each item in Claude response must be an object, got {type(item).__name__}")
        if "id" not in item or "category" not in item:
            raise ValueError(f"Claude response item missing 'id' or 'category': {item}")
        result[str(item["id"])] = str(item["category"])

    return result


def classify_with_claude(
    records: list[NormalizedRecord],
    config: CategoryConfig,
    client: "_anthropic.Anthropic | None" = None,
    model: str = _DEFAULT_MODEL,
) -> list[tuple[str, str]]:
    """Classify inquiries using Claude AI with per-message keyword fallback.

    Sends all records to Claude in a single API call. If Claude's response is
    unparseable or missing IDs, all records fall back to keyword classification.
    If Claude provides an invalid category for a specific record, that record
    falls back to keyword classification individually.

    Args:
        records: Normalized inquiry records to classify.
        config: Category configuration with valid category names.
        client: Optional pre-created Anthropic client (useful for testing/mocking).
                If None, a new client is created via `create_client()`.
        model: Claude model ID to use. Defaults to claude-sonnet-4-6.

    Returns:
        List of `(category, method)` tuples parallel to `records`.
        `method` is `'claude'` when Claude classified successfully, `'keyword'`
        when keyword fallback was used.
    """
    if not records:
        return []

    category_names = config.category_names

    if client is None:
        client = create_client()

    user_message = _build_user_message(records, category_names)

    try:
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        response_text = message.content[0].text
        id_to_category = _parse_claude_response(response_text, records)
    except Exception as exc:  # noqa: BLE001 — broad catch, log and fall back
        print(
            f"Warning: Claude classification failed for entire batch ({exc}); "
            "falling back to keyword classification for all messages.",
            file=sys.stderr,
        )
        # Full batch fallback
        return [
            (classify(rec, category_names), "keyword")
            for rec in records
        ]

    # Per-message result assembly with individual fallback
    results: list[tuple[str, str]] = []
    for rec in records:
        claude_category = id_to_category.get(rec.inquiry_id)

        if claude_category is None:
            print(
                f"Warning: Claude did not return a category for inquiry {rec.inquiry_id!r}; "
                "falling back to keyword classification.",
                file=sys.stderr,
            )
            results.append((classify(rec, category_names), "keyword"))
        elif claude_category not in category_names:
            print(
                f"Warning: Claude returned unknown category {claude_category!r} "
                f"for inquiry {rec.inquiry_id!r}; falling back to keyword classification.",
                file=sys.stderr,
            )
            results.append((classify(rec, category_names), "keyword"))
        else:
            results.append((claude_category, "claude"))

    return results
