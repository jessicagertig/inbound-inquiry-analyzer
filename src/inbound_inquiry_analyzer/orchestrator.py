"""Per-message classification orchestrator.

Coordinates between Claude classification and keyword-based fallback.

Strategy:
- If a client is available (API key set) and keyword_only=False, attempt
  Claude classification for each message individually.
- On any API error for a single message, fall back to keyword classification
  for that message only. Successfully classified messages keep their result.
- When keyword_only=True or no client is available, use keyword classification
  for all messages.

This per-message granularity means partial Claude failures don't discard
successfully classified results from earlier messages.
"""
from __future__ import annotations

import logging

from inbound_inquiry_analyzer.classifier import classify as keyword_classify
from inbound_inquiry_analyzer.claude_classifier import classify_with_claude
from inbound_inquiry_analyzer.normalizer import NormalizedRecord

logger = logging.getLogger(__name__)

# Classification method labels reported back to callers
METHOD_CLAUDE = "claude"
METHOD_KEYWORD = "keyword"
METHOD_MIXED = "mixed"


def classify_all(
    records: list[NormalizedRecord],
    categories: list[str],
    *,
    client=None,
    keyword_only: bool = False,
) -> tuple[list[str], str]:
    """Classify all records, returning predictions and the method used.

    Args:
        records: List of normalized inquiry records.
        categories: List of valid category names from config.
        client: Optional initialized Anthropic client. If None, keyword
                classification is used for all messages.
        keyword_only: When True, skip Claude entirely regardless of client.

    Returns:
        A tuple of (predictions, method) where:
        - predictions is a list of category strings, one per record.
        - method is one of METHOD_CLAUDE, METHOD_KEYWORD, or METHOD_MIXED.
    """
    if keyword_only or client is None:
        predictions = [keyword_classify(r, categories) for r in records]
        return predictions, METHOD_KEYWORD

    predictions: list[str] = []
    claude_count = 0
    keyword_count = 0

    for record in records:
        try:
            category = classify_with_claude(record, categories, client)
            predictions.append(category)
            claude_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Claude classification failed for record %r, falling back to keyword: %s",
                getattr(record, "subject", ""),
                exc,
            )
            category = keyword_classify(record, categories)
            predictions.append(category)
            keyword_count += 1

    if keyword_count == 0:
        method = METHOD_CLAUDE
    elif claude_count == 0:
        method = METHOD_KEYWORD
    else:
        method = METHOD_MIXED

    return predictions, method
