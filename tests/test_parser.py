"""Tests for parser.py: Intercom, contact form, auto-detect, and CSV parsing."""
import csv
import io
import json
import os
import tempfile

import pytest

from inbound_inquiry_analyzer.parser import (
    SOURCE_CONTACT_FORM,
    SOURCE_INTERCOM,
    parse_contact_form,
    parse_input,
    parse_intercom,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

INTERCOM_RECORD = {
    "id": "abc123",
    "state": "open",
    "subject": "Can't log in",
    "first_message": "<p>Hello, I can't sign in to my account.</p>",
    "contact_email": "user@example.com",
    "contact_name": "Jane Doe",
    "created_at": 1700000000,
}

CONTACT_FORM_RECORD = {
    "id": 42,
    "subject": "Pricing question",
    "body": "What is the cost of the pro plan?",
    "reply_to_email": "alice@example.com",
    "created_at": "2024-01-15",
}


# ---------------------------------------------------------------------------
# parse_intercom tests
# ---------------------------------------------------------------------------

class TestParseIntercom:
    def test_single_dict(self):
        result = parse_intercom(INTERCOM_RECORD)
        assert len(result) == 1
        assert result[0]["id"] == "abc123"
        assert result[0]["_source_type"] == SOURCE_INTERCOM

    def test_json_string_single(self):
        result = parse_intercom(json.dumps(INTERCOM_RECORD))
        assert len(result) == 1
        assert result[0]["subject"] == "Can't log in"

    def test_array_of_dicts(self):
        result = parse_intercom([INTERCOM_RECORD, INTERCOM_RECORD])
        assert len(result) == 2

    def test_json_string_array(self):
        result = parse_intercom(json.dumps([INTERCOM_RECORD]))
        assert len(result) == 1

    def test_html_preserved(self):
        result = parse_intercom(INTERCOM_RECORD)
        assert "<p>" in result[0]["first_message"]

    def test_missing_required_field_raises(self):
        bad = {k: v for k, v in INTERCOM_RECORD.items() if k != "contact_email"}
        with pytest.raises(ValueError, match="contact_email"):
            parse_intercom(bad)

    def test_missing_id_raises(self):
        bad = {k: v for k, v in INTERCOM_RECORD.items() if k != "id"}
        with pytest.raises(ValueError, match="id"):
            parse_intercom(bad)

    def test_missing_first_message_raises(self):
        bad = {k: v for k, v in INTERCOM_RECORD.items() if k != "first_message"}
        with pytest.raises(ValueError, match="first_message"):
            parse_intercom(bad)

    def test_source_type_tag(self):
        result = parse_intercom(INTERCOM_RECORD)
        assert result[0]["_source_type"] == SOURCE_INTERCOM

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_intercom("not-json")


# ---------------------------------------------------------------------------
# parse_contact_form tests
# ---------------------------------------------------------------------------

class TestParseContactForm:
    def test_single_dict(self):
        result = parse_contact_form(CONTACT_FORM_RECORD)
        assert len(result) == 1
        assert result[0]["id"] == 42
        assert result[0]["_source_type"] == SOURCE_CONTACT_FORM

    def test_json_string(self):
        result = parse_contact_form(json.dumps(CONTACT_FORM_RECORD))
        assert len(result) == 1

    def test_array(self):
        result = parse_contact_form([CONTACT_FORM_RECORD, CONTACT_FORM_RECORD])
        assert len(result) == 2

    def test_missing_body_raises(self):
        bad = {k: v for k, v in CONTACT_FORM_RECORD.items() if k != "body"}
        with pytest.raises(ValueError, match="body"):
            parse_contact_form(bad)

    def test_missing_reply_to_email_raises(self):
        bad = {k: v for k, v in CONTACT_FORM_RECORD.items() if k != "reply_to_email"}
        with pytest.raises(ValueError, match="reply_to_email"):
            parse_contact_form(bad)

    def test_source_type_tag(self):
        result = parse_contact_form(CONTACT_FORM_RECORD)
        assert result[0]["_source_type"] == SOURCE_CONTACT_FORM


# ---------------------------------------------------------------------------
# parse_input auto-detect tests
# ---------------------------------------------------------------------------

class TestParseInputAutoDetect:
    def test_intercom_json_auto_detect(self):
        result = parse_input(json.dumps(INTERCOM_RECORD))
        assert len(result) == 1
        assert result[0]["_source_type"] == SOURCE_INTERCOM

    def test_contact_form_json_auto_detect(self):
        result = parse_input(json.dumps(CONTACT_FORM_RECORD))
        assert len(result) == 1
        assert result[0]["_source_type"] == SOURCE_CONTACT_FORM

    def test_intercom_dict_auto_detect(self):
        result = parse_input(INTERCOM_RECORD)
        assert result[0]["_source_type"] == SOURCE_INTERCOM

    def test_contact_form_dict_auto_detect(self):
        result = parse_input(CONTACT_FORM_RECORD)
        assert result[0]["_source_type"] == SOURCE_CONTACT_FORM

    def test_format_hint_intercom_overrides(self):
        result = parse_input(INTERCOM_RECORD, format_hint=SOURCE_INTERCOM)
        assert result[0]["_source_type"] == SOURCE_INTERCOM

    def test_format_hint_contact_form_overrides(self):
        result = parse_input(CONTACT_FORM_RECORD, format_hint=SOURCE_CONTACT_FORM)
        assert result[0]["_source_type"] == SOURCE_CONTACT_FORM

    def test_ambiguous_input_raises(self):
        with pytest.raises(ValueError, match="Cannot determine"):
            parse_input({"foo": "bar", "baz": "qux"})

    def test_file_path_json_intercom(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text(json.dumps(INTERCOM_RECORD))
        result = parse_input(f)
        assert result[0]["_source_type"] == SOURCE_INTERCOM

    def test_file_path_json_contact_form(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text(json.dumps(CONTACT_FORM_RECORD))
        result = parse_input(f)
        assert result[0]["_source_type"] == SOURCE_CONTACT_FORM

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            parse_input(tmp_path / "nonexistent.json")

    def test_array_json(self):
        result = parse_input(json.dumps([INTERCOM_RECORD, INTERCOM_RECORD]))
        assert len(result) == 2

    # CSV tests
    def test_csv_intercom_auto_detect(self, tmp_path):
        f = tmp_path / "data.csv"
        fieldnames = list(INTERCOM_RECORD.keys())
        with open(f, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(INTERCOM_RECORD)
        result = parse_input(f)
        assert result[0]["_source_type"] == SOURCE_INTERCOM

    def test_csv_contact_form_auto_detect(self, tmp_path):
        f = tmp_path / "data.csv"
        fieldnames = list(CONTACT_FORM_RECORD.keys())
        with open(f, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow({k: str(v) for k, v in CONTACT_FORM_RECORD.items()})
        result = parse_input(f)
        assert result[0]["_source_type"] == SOURCE_CONTACT_FORM

    def test_csv_with_format_hint(self, tmp_path):
        f = tmp_path / "data.csv"
        fieldnames = list(INTERCOM_RECORD.keys())
        with open(f, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(INTERCOM_RECORD)
        result = parse_input(f, format_hint=SOURCE_INTERCOM)
        assert result[0]["_source_type"] == SOURCE_INTERCOM
