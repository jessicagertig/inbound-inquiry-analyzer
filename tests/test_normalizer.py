"""Tests for normalizer.py: Intercom and contact form normalization, dispatcher."""
import pytest

from inbound_inquiry_analyzer.normalizer import (
    NormalizedRecord,
    normalize,
    normalize_contact_form,
    normalize_intercom,
)
from inbound_inquiry_analyzer.parser import SOURCE_CONTACT_FORM, SOURCE_INTERCOM

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

INTERCOM_RAW = {
    "_source_type": SOURCE_INTERCOM,
    "id": "ic-001",
    "state": "open",
    "subject": "Can't log in",
    "first_message": "<p>I can't sign in.</p>",
    "contact_email": "user@example.com",
    "contact_name": "Jane Doe",
    "created_at": 1700000000,
}

CONTACT_FORM_RAW = {
    "_source_type": SOURCE_CONTACT_FORM,
    "id": 42,
    "subject": "Pricing question",
    "body": "What is the pro plan cost?",
    "reply_to_email": "alice@example.com",
    "created_at": "2024-01-15",
}


# ---------------------------------------------------------------------------
# NormalizedRecord dataclass
# ---------------------------------------------------------------------------

class TestNormalizedRecord:
    def test_fields_exist(self):
        rec = NormalizedRecord(
            inquiry_id="x", source="Intercom", received_at_date="2024-01-01",
            received_at_ts=1704067200.0, from_name="A", from_email="a@b.com",
            subject="Hi", message_body="Hello",
        )
        assert rec.inquiry_id == "x"
        assert rec.source == "Intercom"


# ---------------------------------------------------------------------------
# normalize_intercom tests
# ---------------------------------------------------------------------------

class TestNormalizeIntercom:
    def test_basic_mapping(self):
        rec = normalize_intercom(INTERCOM_RAW)
        assert isinstance(rec, NormalizedRecord)
        assert rec.inquiry_id == "ic-001"
        assert rec.source == "Intercom"
        assert rec.from_name == "Jane Doe"
        assert rec.from_email == "user@example.com"
        assert rec.subject == "Can't log in"
        assert rec.message_body == "<p>I can't sign in.</p>"

    def test_received_at_ts_matches_original(self):
        rec = normalize_intercom(INTERCOM_RAW)
        assert rec.received_at_ts == 1700000000.0

    def test_received_at_date_format(self):
        rec = normalize_intercom(INTERCOM_RAW)
        # Should be YYYY-MM-DD
        parts = rec.received_at_date.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year
        assert len(parts[1]) == 2  # month
        assert len(parts[2]) == 2  # day

    def test_html_preserved(self):
        rec = normalize_intercom(INTERCOM_RAW)
        assert "<p>" in rec.message_body

    def test_contact_name_optional(self):
        raw = {**INTERCOM_RAW}
        del raw["contact_name"]
        rec = normalize_intercom(raw)
        assert rec.from_name == ""

    def test_contact_name_none_becomes_empty(self):
        raw = {**INTERCOM_RAW, "contact_name": None}
        rec = normalize_intercom(raw)
        assert rec.from_name == ""

    def test_id_converted_to_str(self):
        raw = {**INTERCOM_RAW, "id": 12345}
        rec = normalize_intercom(raw)
        assert rec.inquiry_id == "12345"

    def test_known_timestamp_date(self):
        # 1700000000 UTC = 2023-11-14
        rec = normalize_intercom(INTERCOM_RAW)
        assert rec.received_at_date == "2023-11-14"

    def test_invalid_timestamp_raises(self):
        raw = {**INTERCOM_RAW, "created_at": "not-a-number"}
        with pytest.raises(ValueError, match="Unix timestamp"):
            normalize_intercom(raw)


# ---------------------------------------------------------------------------
# normalize_contact_form tests
# ---------------------------------------------------------------------------

class TestNormalizeContactForm:
    def test_basic_mapping(self):
        rec = normalize_contact_form(CONTACT_FORM_RAW)
        assert isinstance(rec, NormalizedRecord)
        assert rec.inquiry_id == "42"
        assert rec.source == "In-app contact form"
        assert rec.from_name == ""
        assert rec.from_email == "alice@example.com"
        assert rec.subject == "Pricing question"
        assert rec.message_body == "What is the pro plan cost?"

    def test_from_name_is_empty(self):
        rec = normalize_contact_form(CONTACT_FORM_RAW)
        assert rec.from_name == ""

    def test_received_at_date_preserved(self):
        rec = normalize_contact_form(CONTACT_FORM_RAW)
        assert rec.received_at_date == "2024-01-15"

    def test_received_at_ts_is_midnight_utc(self):
        rec = normalize_contact_form(CONTACT_FORM_RAW)
        # 2024-01-15 00:00:00 UTC
        import calendar
        from datetime import datetime, timezone
        expected = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        assert rec.received_at_ts == expected

    def test_numeric_id_to_str(self):
        rec = normalize_contact_form(CONTACT_FORM_RAW)
        assert rec.inquiry_id == "42"

    def test_invalid_date_raises(self):
        raw = {**CONTACT_FORM_RAW, "created_at": "not-a-date"}
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            normalize_contact_form(raw)


# ---------------------------------------------------------------------------
# normalize() dispatcher tests
# ---------------------------------------------------------------------------

class TestNormalizeDispatcher:
    def test_dispatches_intercom(self):
        rec = normalize(INTERCOM_RAW)
        assert rec.source == "Intercom"

    def test_dispatches_contact_form(self):
        rec = normalize(CONTACT_FORM_RAW)
        assert rec.source == "In-app contact form"

    def test_missing_source_type_raises(self):
        raw = {**INTERCOM_RAW}
        del raw["_source_type"]
        with pytest.raises(ValueError, match="_source_type"):
            normalize(raw)

    def test_unknown_source_type_raises(self):
        raw = {**INTERCOM_RAW, "_source_type": "unknown"}
        with pytest.raises(ValueError, match="Unknown source type"):
            normalize(raw)
