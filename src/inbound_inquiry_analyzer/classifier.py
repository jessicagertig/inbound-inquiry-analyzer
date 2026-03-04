"""Keyword-based inquiry classifier.

Assigns a Predicted Category to each normalized inquiry using pattern/keyword matching.

Strategy:
- Rules are checked in priority order (first match wins) to resolve conflicts.
- Each rule is a (category_name, list_of_keyword_patterns) pair.
- Patterns are matched case-insensitively against a combined text of subject + message_body.
- Falls back to 'Unclear' when no rule matches.
- All returned categories are valid entries from the configured category list.

This approach was chosen over an LLM classifier because it is:
- Simpler to implement, test, and audit
- Offline (no external API calls or network access)
- Deterministic and fast
"""
from __future__ import annotations

import re

from inbound_inquiry_analyzer.normalizer import NormalizedRecord

# Priority-ordered classification rules.
# Each entry: (category_name, list_of_regex_patterns)
# First matching rule wins. Patterns are case-insensitive.
_RULES: list[tuple[str, list[str]]] = [
    (
        "Request for data deletion",
        [
            r"\bdelete\s+my\s+(account|data|information)\b",
            r"\bremove\s+my\s+(account|data|information)\b",
            r"\bdata\s+deletion\b",
            r"\bright\s+to\s+(be\s+forgotten|erasure)\b",
            r"\bGDPR\b",
            r"\bprivacy\s+(request|deletion)\b",
            r"\berase\s+my\s+data\b",
        ],
    ),
    (
        "Wrong email address (not intended for Polymer)",
        [
            r"\bwrong\s+email\b",
            r"\bnot\s+intended\s+for\b",
            r"\bwrong\s+address\b",
            r"\bwrong\s+recipient\b",
            r"\bmisdelivered\b",
            r"\bsent\s+(to\s+)?the\s+wrong\b",
            r"\bintended\s+for\s+(someone\s+else|another)\b",
        ],
    ),
    (
        "Advertising or solicitation",
        [
            r"\bpartnership\s+opportunit\b",
            r"\bsponsor(ship)?\b",
            r"\badvertis(e|ing|ement)\b",
            r"\bpromotion(al)?\b",
            r"\bmarketing\s+(opportunit|proposal|offer)\b",
            r"\bsolicitat\b",
            r"\bcollab(orat)?\b",
            r"\baffiliate\s+program\b",
            r"\bguest\s+post\b",
            r"\blink\s+exchange\b",
            r"\bour\s+(service|product|solution|software|tool)s?\s+(can|could|will|would)\b",
        ],
    ),
    (
        "Issue with login",
        [
            r"\b(can'?t|cannot|unable\s+to)\s+(log\s*in|sign\s*in|access|login)\b",
            r"\b(forgot|reset|recover)\s+(my\s+)?password\b",
            r"\bpassword\s+(reset|recovery|expired|incorrect|wrong)\b",
            r"\blog\s*in\s+(issue|problem|error|fail)\b",
            r"\bsign[\s-]in\s+(issue|problem|error|fail)\b",
            r"\bauthentication\s+(fail|error|issue|problem)\b",
            r"\baccount\s+(locked|suspended|disabled|blocked)\b",
            r"\btwo[\s-]factor\b",
            r"\b2fa\b",
            r"\bsso\s+(issue|problem|error|fail)\b",
            r"\blogin\b",
            r"\bsign\s*in\b",
        ],
    ),
    (
        "Refund request",
        [
            r"\brefund\b",
            r"\bmoney\s+back\b",
            r"\bchargeback\b",
            r"\bdispute\s+(charge|payment|transaction)\b",
            r"\bovercharged\b",
            r"\bdouble\s+charged\b",
            r"\bwant\s+(my\s+)?(money|payment)\s+back\b",
        ],
    ),
    (
        "Inquiry about plan or pricing",
        [
            r"\bpric(e|ing|es)\b",
            r"\bplan(s)?\b",
            r"\bcost(s|ing)?\b",
            r"\bsubscription\b",
            r"\btier(s)?\b",
            r"\bupgrade\b",
            r"\bdowngrade\b",
            r"\bhow\s+much\b",
            r"\bquot(e|ation)\b",
            r"\bbilling\b",
            r"\binvoice\b",
            r"\bpayment\s+plan\b",
            r"\benterprise\s+plan\b",
        ],
    ),
    (
        "Migration",
        [
            r"\bmi?grat(e|ion|ing)\b",
            r"\bimport(ing)?\s+(data|from|my)\b",
            r"\bexport(ing)?\s+(data|to|my)\b",
            r"\btransfer(ring)?\s+(data|from|to)\b",
            r"\bmoving\s+(from|to|data)\b",
            r"\bswitch(ing)?\s+(from|to)\b",
            r"\bdata\s+(import|export|transfer)\b",
        ],
    ),
    (
        "Knowledge base help",
        [
            r"\bhow\s+(do\s+I|to|does)\b",
            r"\bwhere\s+(can\s+I|do\s+I|is)\b",
            r"\bdocumentation\b",
            r"\bdocs?\b",
            r"\btutorial\b",
            r"\bguide\b",
            r"\bhelp\s+(me\s+)?(find|understand|with)\b",
            r"\bknowledge\s+base\b",
            r"\bfaq\b",
            r"\bexplain\b",
            r"\bwhat\s+is\b",
        ],
    ),
    (
        "Feature help",
        [
            r"\bfeature\b",
            r"\bfunctionality\b",
            r"\bhow\s+to\s+(use|enable|disable|configure|set\s+up)\b",
            r"\bset\s*up\b",
            r"\bconfigur(e|ation|ing)\b",
            r"\bintegrat(e|ion|ing)\b",
            r"\bapi\b",
            r"\bwebhook\b",
            r"\bworkflow\b",
            r"\bautom(ate|ation|ating)\b",
        ],
    ),
]

_UNCLEAR = "Unclear"


def classify(record: NormalizedRecord, categories: list[str]) -> str:
    """Classify an inquiry into a category using keyword matching.

    Searches both subject and message_body (case-insensitively) against a
    priority-ordered list of keyword rules. The first matching rule wins.
    Returns 'Unclear' if no rule matches.

    Args:
        record: Normalized inquiry record.
        categories: List of valid category names from config (used to validate
                    that rules only return configured categories).

    Returns:
        A category name from the configured categories list, or 'Unclear'.
    """
    text = f"{record.subject} {record.message_body}".lower()

    for category, patterns in _RULES:
        if category not in categories:
            # Skip rules for categories not in current config
            continue
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return category

    # No rule matched — check if "Unclear" is in the category list
    if _UNCLEAR in categories:
        return _UNCLEAR
    # Fallback: return last category as catch-all (shouldn't happen with correct config)
    return categories[-1] if categories else _UNCLEAR
