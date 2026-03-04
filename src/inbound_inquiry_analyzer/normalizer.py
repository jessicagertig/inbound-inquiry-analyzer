"""Record normalization: converts raw parsed records into NormalizedRecord instances.

NormalizedRecord is the single internal data format used by all downstream modules
(classifier, xlsx_writer, cli).

Two normalizers:
- normalize_intercom: handles Intercom JSON shape (Unix timestamp for created_at)
- normalize_contact_form: handles in-app contact form shape (YYYY-MM-DD for created_at)

A normalize() dispatcher routes records by their '_source_type' tag.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class NormalizedRecord:
    """Unified internal representation of an inbound inquiry."""
    inquiry_id: str
    source: str
    received_at_date: str  # YYYY-MM-DD
    received_at_ts: float  # Unix timestamp (seconds since epoch, UTC)
    from_name: str
    from_email: str
    subject: str
    message_body: str


def normalize_intercom(record: dict) -> NormalizedRecord:
    """Normalize a raw Intercom record into a NormalizedRecord.

    Field mapping:
    - id -> inquiry_id (converted to str)
    - 'Intercom' -> source (hardcoded)
    - created_at (Unix timestamp int/float) -> received_at_ts AND received_at_date (YYYY-MM-DD)
    - contact_name -> from_name (defaults to '' if missing)
    - contact_email -> from_email
    - subject -> subject
    - first_message -> message_body (HTML preserved as-is per spec)

    Timezone note: Intercom timestamps are Unix epoch (UTC-agnostic integers).
    We convert to YYYY-MM-DD using UTC date for consistency.
    """
    inquiry_id = str(record["id"])
    source = "Intercom"

    # created_at is a Unix timestamp (int or float)
    try:
        ts = float(record["created_at"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Intercom record {inquiry_id}: 'created_at' must be a numeric Unix timestamp, "
            f"got {record['created_at']!r}"
        ) from exc

    received_at_ts = ts
    received_at_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    from_name = str(record.get("contact_name", "") or "")
    from_email = str(record["contact_email"])
    subject = str(record["subject"])
    message_body = str(record["first_message"])  # HTML preserved as-is

    return NormalizedRecord(
        inquiry_id=inquiry_id,
        source=source,
        received_at_date=received_at_date,
        received_at_ts=received_at_ts,
        from_name=from_name,
        from_email=from_email,
        subject=subject,
        message_body=message_body,
    )


def normalize_contact_form(record: dict) -> NormalizedRecord:
    """Normalize a raw in-app contact form record into a NormalizedRecord.

    Field mapping:
    - id -> inquiry_id (converted to str)
    - 'In-app contact form' -> source (hardcoded)
    - created_at (YYYY-MM-DD string) -> received_at_date AND received_at_ts (midnight UTC)
    - '' -> from_name (empty; contact form does not include sender name)
    - reply_to_email -> from_email
    - subject -> subject
    - body -> message_body

    Timezone note: created_at is a date string (YYYY-MM-DD). We convert to Unix timestamp
    as midnight UTC (00:00:00 UTC) for the given date. This is arbitrary but consistent —
    contact form submissions don't carry sub-day precision in the input schema.
    """
    inquiry_id = str(record["id"])
    source = "In-app contact form"

    date_str = str(record["created_at"])
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(
            f"Contact form record {inquiry_id}: 'created_at' must be YYYY-MM-DD, "
            f"got {date_str!r}"
        ) from exc

    received_at_date = date_str
    received_at_ts = dt.timestamp()  # midnight UTC as Unix float

    from_name = ""  # contact form does not provide sender name
    from_email = str(record["reply_to_email"])
    subject = str(record["subject"])
    message_body = str(record["body"])

    return NormalizedRecord(
        inquiry_id=inquiry_id,
        source=source,
        received_at_date=received_at_date,
        received_at_ts=received_at_ts,
        from_name=from_name,
        from_email=from_email,
        subject=subject,
        message_body=message_body,
    )


# Import here to avoid circular at module level; parser constants define source tags
_SOURCE_INTERCOM = "intercom"
_SOURCE_CONTACT_FORM = "contact_form"


def normalize(record: dict) -> NormalizedRecord:
    """Dispatcher: route a raw tagged record to the correct normalizer.

    The record must have a '_source_type' key set by the parser.

    Args:
        record: Raw record dict with '_source_type' tag.

    Returns:
        NormalizedRecord instance.

    Raises:
        ValueError: If '_source_type' is missing or unrecognized.
    """
    source_type = record.get("_source_type")
    if source_type == _SOURCE_INTERCOM:
        return normalize_intercom(record)
    elif source_type == _SOURCE_CONTACT_FORM:
        return normalize_contact_form(record)
    elif source_type is None:
        raise ValueError(
            "Record is missing '_source_type' tag. "
            "Pass records through parse_input() before normalizing."
        )
    else:
        raise ValueError(
            f"Unknown source type {source_type!r}. "
            f"Expected 'intercom' or 'contact_form'."
        )
