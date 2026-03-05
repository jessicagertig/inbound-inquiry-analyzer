"""Claude-based inquiry classifier.

Sends each inquiry's subject and message body to Claude along with the
full list of configured categories. Claude returns exactly one category
string, which may be a new category not in the predefined list when none
of the existing options fit well.

Design notes:
- A single message per inquiry is sent (no conversation history).
- The prompt instructs Claude to prefer existing categories and only
  propose new ones when the inquiry clearly does not fit any option.
- The response is stripped of whitespace; no further parsing is needed
  because Claude is instructed to return only the category name.
"""
from __future__ import annotations

from inbound_inquiry_analyzer.api_client import get_model
from inbound_inquiry_analyzer.normalizer import NormalizedRecord

_SYSTEM_PROMPT = (
    "You are an expert customer-support triage assistant. "
    "Your task is to classify inbound customer inquiries into exactly one category.\n\n"
    "Rules:\n"
    "1. Choose from the provided list of categories whenever possible.\n"
    "2. Only propose a NEW category name when the inquiry clearly does not fit any "
    "   existing option.\n"
    "3. Respond with ONLY the category name — no explanation, no punctuation, "
    "   no surrounding quotes.\n"
    "4. If the message is empty or unintelligible, respond with: Unclear"
)


def _build_user_message(record: NormalizedRecord, categories: list[str]) -> str:
    category_list = "\n".join(f"- {c}" for c in categories)
    subject_line = f"Subject: {record.subject}\n" if record.subject else ""
    body = record.message_body or ""
    return (
        f"Categories:\n{category_list}\n\n"
        f"{subject_line}"
        f"Message:\n{body}"
    )


def classify_with_claude(
    record: NormalizedRecord,
    categories: list[str],
    client,
) -> str:
    """Classify one inquiry using the Claude API.

    Args:
        record: Normalized inquiry record.
        categories: List of valid category names from config.
        client: Initialized anthropic.Anthropic client instance.

    Returns:
        A category string. May be a new category not in *categories* if
        Claude determines none of the existing options fit.

    Raises:
        anthropic.APIError and subclasses on API failures (let callers handle).
    """
    response = client.messages.create(
        model=get_model(),
        max_tokens=64,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_user_message(record, categories),
            }
        ],
    )
    # Extract the text from the first content block
    category = response.content[0].text.strip()
    return category if category else "Unclear"
