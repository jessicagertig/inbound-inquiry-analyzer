"""Tests for classifier.py: keyword-based category assignment."""
import pytest

from inbound_inquiry_analyzer.classifier import classify
from inbound_inquiry_analyzer.normalizer import NormalizedRecord

CATEGORIES = [
    "Issue with login",
    "Inquiry about plan or pricing",
    "Request for data deletion",
    "Wrong email address (not intended for Polymer)",
    "Advertising or solicitation",
    "Knowledge base help",
    "Feature help",
    "Migration",
    "Refund request",
    "Other",
    "Unclear",
]


def make_record(subject="", body="") -> NormalizedRecord:
    return NormalizedRecord(
        inquiry_id="test-1",
        source="Intercom",
        received_at_date="2024-01-01",
        received_at_ts=1704067200.0,
        from_name="Test User",
        from_email="test@example.com",
        subject=subject,
        message_body=body,
    )


class TestClassify:
    def test_login_keyword_in_subject(self):
        rec = make_record(subject="Can't login to my account")
        assert classify(rec, CATEGORIES) == "Issue with login"

    def test_login_keyword_password_reset(self):
        rec = make_record(body="I forgot my password and need to reset it")
        assert classify(rec, CATEGORIES) == "Issue with login"

    def test_login_keyword_sign_in(self):
        rec = make_record(subject="Sign in issue", body="I cannot sign in anymore")
        assert classify(rec, CATEGORIES) == "Issue with login"

    def test_pricing_keyword(self):
        rec = make_record(subject="Question about pricing")
        assert classify(rec, CATEGORIES) == "Inquiry about plan or pricing"

    def test_plan_keyword(self):
        rec = make_record(body="What plans do you offer?")
        assert classify(rec, CATEGORIES) == "Inquiry about plan or pricing"

    def test_cost_keyword(self):
        rec = make_record(body="How much does it cost?")
        assert classify(rec, CATEGORIES) == "Inquiry about plan or pricing"

    def test_data_deletion_keyword(self):
        rec = make_record(body="Please delete my account and all my data")
        assert classify(rec, CATEGORIES) == "Request for data deletion"

    def test_gdpr_keyword(self):
        rec = make_record(subject="GDPR request")
        assert classify(rec, CATEGORIES) == "Request for data deletion"

    def test_wrong_email_keyword(self):
        rec = make_record(subject="Wrong email address", body="This was not intended for me")
        assert classify(rec, CATEGORIES) == "Wrong email address (not intended for Polymer)"

    def test_not_intended_keyword(self):
        rec = make_record(body="I think this email was not intended for Polymer")
        assert classify(rec, CATEGORIES) == "Wrong email address (not intended for Polymer)"

    def test_refund_keyword(self):
        rec = make_record(body="I would like a refund for my subscription")
        assert classify(rec, CATEGORIES) == "Refund request"

    def test_migration_keyword(self):
        rec = make_record(body="I need help migrating my data from another platform")
        assert classify(rec, CATEGORIES) == "Migration"

    def test_unclear_fallback(self):
        rec = make_record(subject="Hello", body="Just wanted to say hi")
        assert classify(rec, CATEGORIES) == "Unclear"

    def test_case_insensitive(self):
        rec = make_record(subject="PRICING QUESTION")
        assert classify(rec, CATEGORIES) == "Inquiry about plan or pricing"

    def test_subject_field_matched(self):
        rec = make_record(subject="password reset needed", body="")
        assert classify(rec, CATEGORIES) == "Issue with login"

    def test_message_body_field_matched(self):
        rec = make_record(subject="help", body="I need to reset my password")
        assert classify(rec, CATEGORIES) == "Issue with login"

    def test_all_returned_categories_are_valid(self):
        test_cases = [
            make_record(subject="login problem"),
            make_record(subject="pricing question"),
            make_record(subject="delete my data"),
            make_record(subject="wrong email"),
            make_record(subject="refund please"),
            make_record(subject="migration help"),
            make_record(subject="random vague message"),
        ]
        for rec in test_cases:
            result = classify(rec, CATEGORIES)
            assert result in CATEGORIES, f"Returned category {result!r} not in config"

    def test_advertising_keyword(self):
        rec = make_record(
            subject="Partnership opportunity",
            body="We would like to advertise our product"
        )
        assert classify(rec, CATEGORIES) == "Advertising or solicitation"
