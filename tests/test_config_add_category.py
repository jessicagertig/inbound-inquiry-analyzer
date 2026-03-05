"""Tests for CategoryConfig.add_category (new category handling)."""
import pytest
from inbound_inquiry_analyzer.config import CategoryConfig


def _base_config():
    return CategoryConfig(
        categories=[
            {"name": "Issue with login", "color": "#FF0000"},
            {"name": "Refund request", "color": "#00FF00"},
            {"name": "Unclear", "color": "#CCCCCC"},
        ],
        sources=["Intercom"],
    )


def test_add_new_category_appears_in_names():
    cfg = _base_config()
    cfg.add_category("Accessibility request")
    assert "Accessibility request" in cfg.category_names


def test_add_new_category_gets_default_color():
    cfg = _base_config()
    cfg.add_category("Accessibility request")
    assert cfg.color_map["Accessibility request"] == "#E0E0E0"


def test_add_new_category_custom_color():
    cfg = _base_config()
    cfg.add_category("New Cat", color="#ABCDEF")
    assert cfg.color_map["New Cat"] == "#ABCDEF"


def test_add_existing_category_is_noop():
    cfg = _base_config()
    original_count = len(cfg.categories)
    cfg.add_category("Refund request")
    assert len(cfg.categories) == original_count
    # Color should remain unchanged
    assert cfg.color_map["Refund request"] == "#00FF00"


def test_add_category_included_in_categories_list():
    cfg = _base_config()
    cfg.add_category("Brand new")
    entry = next(c for c in cfg.categories if c["name"] == "Brand new")
    assert entry["color"] == "#E0E0E0"
