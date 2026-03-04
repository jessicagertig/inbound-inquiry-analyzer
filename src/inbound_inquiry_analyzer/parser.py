"""Input ingestion and parsing for inbound inquiries.

Supports two JSON shapes:
- Intercom: {id, state, subject, first_message (HTML), contact_email, contact_name, created_at (Unix timestamp)}
- In-app contact form: {id, subject, body, reply_to_email, created_at (YYYY-MM-DD string)}

Also supports CSV files where field names are detected to determine format.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

# Source type tags attached to raw records for downstream routing
SOURCE_INTERCOM = "intercom"
SOURCE_CONTACT_FORM = "contact_form"

# Required fields per format
_INTERCOM_REQUIRED = {"id", "subject", "first_message", "contact_email", "created_at"}
_CONTACT_FORM_REQUIRED = {"id", "subject", "body", "reply_to_email", "created_at"}

# Distinguishing field sets for auto-detection
_INTERCOM_SIGNATURE = {"first_message", "contact_email"}
_CONTACT_FORM_SIGNATURE = {"body", "reply_to_email"}


def parse_intercom(data: str | dict | list) -> list[dict]:
    """Parse Intercom-shaped JSON into a list of raw records.

    Each returned record has a '_source_type' tag set to SOURCE_INTERCOM.

    Args:
        data: JSON string, a single Intercom record dict, or a list of dicts.

    Returns:
        List of raw Intercom record dicts.

    Raises:
        ValueError: If JSON is invalid or required fields are missing.
    """
    records = _to_list(data, "Intercom")
    result = []
    for i, rec in enumerate(records):
        _validate_fields(rec, _INTERCOM_REQUIRED, f"Intercom record {i}")
        rec = dict(rec)
        rec["_source_type"] = SOURCE_INTERCOM
        result.append(rec)
    return result


def parse_contact_form(data: str | dict | list) -> list[dict]:
    """Parse in-app contact form JSON into a list of raw records.

    Each returned record has a '_source_type' tag set to SOURCE_CONTACT_FORM.

    Args:
        data: JSON string, a single contact form record dict, or a list of dicts.

    Returns:
        List of raw contact form record dicts.

    Raises:
        ValueError: If JSON is invalid or required fields are missing.
    """
    records = _to_list(data, "contact form")
    result = []
    for i, rec in enumerate(records):
        _validate_fields(rec, _CONTACT_FORM_REQUIRED, f"contact form record {i}")
        rec = dict(rec)
        rec["_source_type"] = SOURCE_CONTACT_FORM
        result.append(rec)
    return result


def parse_input(
    data: str | Path | dict | list,
    format_hint: str | None = None,
) -> list[dict]:
    """Auto-detect format and parse input into a list of raw tagged records.

    Supports:
    - File path (str or Path): reads file, detects JSON or CSV by extension/content
    - JSON string: parses and detects format by field names
    - Already-parsed dict or list: detects format by field names
    - format_hint: 'intercom' or 'contact_form' to override auto-detection

    Args:
        data: Input as file path, JSON string, dict, or list.
        format_hint: Optional format override ('intercom' or 'contact_form').

    Returns:
        List of raw records, each tagged with '_source_type'.

    Raises:
        ValueError: If format cannot be determined or input is invalid.
    """
    # Resolve file paths
    if isinstance(data, Path) or (isinstance(data, str) and _looks_like_path(data)):
        path = Path(data)
        if not path.exists():
            raise ValueError(f"Input file not found: {path}")
        content = path.read_text(encoding="utf-8")
        # CSV detection by extension
        if path.suffix.lower() == ".csv":
            return _parse_csv(content, format_hint)
        # Otherwise treat as JSON
        data = content

    # At this point data is str (JSON), dict, or list
    if isinstance(data, str):
        # Try CSV if it doesn't look like JSON
        stripped = data.lstrip()
        if stripped and stripped[0] not in ("{", "["):
            return _parse_csv(data, format_hint)
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON input: {exc}") from exc
        data = parsed

    # data is now dict or list
    records = data if isinstance(data, list) else [data]
    if not records:
        return []

    # Determine format
    fmt = format_hint or _detect_format(records[0])
    if fmt == SOURCE_INTERCOM:
        return parse_intercom(records)
    elif fmt == SOURCE_CONTACT_FORM:
        return parse_contact_form(records)
    else:
        raise ValueError(
            f"Cannot determine input format. "
            f"Expected fields for Intercom ({_INTERCOM_SIGNATURE}) or "
            f"contact form ({_CONTACT_FORM_SIGNATURE}). "
            f"Got fields: {set(records[0].keys()) - {'_source_type'}}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _looks_like_path(s: str) -> bool:
    """Heuristic: does this string look like a file path rather than JSON?"""
    s = s.strip()
    if not s:
        return False
    if s[0] in ("{", "[", '"'):
        return False
    # Contains path separators or common extensions
    return "/" in s or "\\" in s or s.endswith((".json", ".csv"))


def _to_list(data: Any, label: str) -> list[dict]:
    """Parse JSON string (if needed) and ensure we have a list of dicts."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for {label}: {exc}") from exc
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError(f"Expected dict or list for {label}, got {type(data).__name__}")


def _validate_fields(record: dict, required: set[str], label: str) -> None:
    """Check that all required fields are present."""
    missing = required - set(record.keys())
    if missing:
        raise ValueError(
            f"Missing required fields in {label}: {sorted(missing)}. "
            f"Record keys: {sorted(record.keys())}"
        )


def _detect_format(record: dict) -> str | None:
    """Detect format from field names of a single record."""
    keys = set(record.keys())
    if _INTERCOM_SIGNATURE.issubset(keys):
        return SOURCE_INTERCOM
    if _CONTACT_FORM_SIGNATURE.issubset(keys):
        return SOURCE_CONTACT_FORM
    return None


def _parse_csv(content: str, format_hint: str | None) -> list[dict]:
    """Parse CSV content into records and detect format from column names."""
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return []

    fmt = format_hint or _detect_format(rows[0])
    if fmt == SOURCE_INTERCOM:
        return parse_intercom(rows)
    elif fmt == SOURCE_CONTACT_FORM:
        return parse_contact_form(rows)
    else:
        raise ValueError(
            f"Cannot determine CSV format from columns: {list(rows[0].keys())}. "
            f"Expected Intercom columns {_INTERCOM_SIGNATURE} or "
            f"contact form columns {_CONTACT_FORM_SIGNATURE}."
        )
