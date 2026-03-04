"""Tests for xlsx_writer.py: workbook structure, drop-downs, fills, and formatting."""
import pytest
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from inbound_inquiry_analyzer.config import CategoryConfig
from inbound_inquiry_analyzer.normalizer import NormalizedRecord
from inbound_inquiry_analyzer.xlsx_writer import generate_workbook

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CATEGORIES = [
    {"name": "Issue with login", "color": "#FFD700"},
    {"name": "Inquiry about plan or pricing", "color": "#90EE90"},
    {"name": "Request for data deletion", "color": "#FFB6C1"},
    {"name": "Wrong email address (not intended for Polymer)", "color": "#ADD8E6"},
    {"name": "Advertising or solicitation", "color": "#D3D3D3"},
    {"name": "Knowledge base help", "color": "#DDA0DD"},
    {"name": "Feature help", "color": "#87CEEB"},
    {"name": "Migration", "color": "#F0E68C"},
    {"name": "Refund request", "color": "#FFA07A"},
    {"name": "Other", "color": "#E0E0E0"},
    {"name": "Unclear", "color": "#FF4500"},
]
SOURCES = ["Intercom", "In-app contact form", "Discord", "Direct email inquiry", "LinkedIn message"]


@pytest.fixture
def config():
    return CategoryConfig(categories=CATEGORIES, sources=SOURCES)


def make_record(
    inquiry_id="test-1",
    source="Intercom",
    date="2024-01-15",
    ts=1705276800.0,
    from_name="Jane Doe",
    from_email="jane@example.com",
    subject="Test subject",
    body="Test body",
) -> NormalizedRecord:
    return NormalizedRecord(
        inquiry_id=inquiry_id,
        source=source,
        received_at_date=date,
        received_at_ts=ts,
        from_name=from_name,
        from_email=from_email,
        subject=subject,
        message_body=body,
    )


@pytest.fixture
def sample_records():
    return [
        make_record("r1", ts=1705276800.0, subject="Login issue"),
        make_record("r2", ts=1705363200.0, subject="Pricing query"),
        make_record("r3", ts=1705190400.0, subject="Delete my data"),
    ]


@pytest.fixture
def sample_predictions():
    return [
        "Issue with login",
        "Inquiry about plan or pricing",
        "Unclear",
    ]


@pytest.fixture
def generated_wb(tmp_path, config, sample_records, sample_predictions):
    output = tmp_path / "test_output.xlsx"
    generate_workbook(sample_records, sample_predictions, config, output)
    return load_workbook(str(output))


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------

class TestWorkbookStructure:
    def test_inquiries_sheet_exists(self, generated_wb):
        assert "Inquiries" in generated_wb.sheetnames

    def test_lists_sheet_exists(self, generated_wb):
        assert "Lists" in generated_wb.sheetnames

    def test_eleven_columns(self, generated_wb):
        ws = generated_wb["Inquiries"]
        headers = [ws.cell(row=1, column=c).value for c in range(1, 12)]
        assert len([h for h in headers if h is not None]) == 11

    def test_column_headers_correct(self, generated_wb):
        ws = generated_wb["Inquiries"]
        expected = [
            "Inquiry ID",
            "Source",
            "Received At (YYYY-MM-DD)",
            "Received At (Timestamp)",
            "From Name",
            "From Email",
            "Subject",
            "Message Body",
            "Predicted Category",
            "Final Category",
            "Notes",
        ]
        for col_idx, expected_header in enumerate(expected, start=1):
            assert ws.cell(row=1, column=col_idx).value == expected_header

    def test_data_rows_count(self, generated_wb, sample_records):
        ws = generated_wb["Inquiries"]
        data_rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if any(v is not None for v in r)]
        assert len(data_rows) == len(sample_records)

    def test_rows_sorted_by_timestamp(self, generated_wb):
        ws = generated_wb["Inquiries"]
        # Column 4 is Received At (Timestamp)
        timestamps = [ws.cell(row=r, column=4).value for r in range(2, 5)]
        assert timestamps == sorted(timestamps)

    def test_final_category_matches_predicted_initially(self, generated_wb):
        ws = generated_wb["Inquiries"]
        for row in range(2, 5):
            predicted = ws.cell(row=row, column=9).value
            final = ws.cell(row=row, column=10).value
            assert predicted == final

    def test_notes_column_is_blank(self, generated_wb):
        ws = generated_wb["Inquiries"]
        for row in range(2, 5):
            assert ws.cell(row=row, column=11).value is None


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------

class TestFormatting:
    def test_header_is_frozen(self, generated_wb):
        ws = generated_wb["Inquiries"]
        assert ws.freeze_panes is not None
        # Frozen at A2 means row 1 stays visible
        assert ws.freeze_panes == "A2"

    def test_auto_filter_enabled(self, generated_wb):
        ws = generated_wb["Inquiries"]
        assert ws.auto_filter.ref is not None

    def test_header_is_bold(self, generated_wb):
        ws = generated_wb["Inquiries"]
        for col in range(1, 12):
            cell = ws.cell(row=1, column=col)
            assert cell.font is not None and cell.font.bold, f"Column {col} header not bold"

    def test_header_has_fill(self, generated_wb):
        ws = generated_wb["Inquiries"]
        for col in range(1, 12):
            cell = ws.cell(row=1, column=col)
            assert cell.fill is not None and cell.fill.fill_type == "solid"

    def test_message_body_column_width_wider(self, generated_wb):
        ws = generated_wb["Inquiries"]
        msg_body_width = ws.column_dimensions["H"].width
        inquiry_id_width = ws.column_dimensions["A"].width
        assert msg_body_width > inquiry_id_width


# ---------------------------------------------------------------------------
# Data validation tests
# ---------------------------------------------------------------------------

class TestDataValidation:
    def test_final_category_has_data_validation(self, generated_wb):
        ws = generated_wb["Inquiries"]
        # Find any validation that covers column J (Final Category)
        dv_list = ws.data_validations.dataValidation
        found = False
        for dv in dv_list:
            if dv.formula1 and "Lists" in dv.formula1:
                for sqref in str(dv.sqref).split():
                    if "J" in sqref:
                        found = True
                        break
        assert found, "No data validation for Final Category (column J)"

    def test_source_has_data_validation(self, generated_wb):
        ws = generated_wb["Inquiries"]
        dv_list = ws.data_validations.dataValidation
        found = False
        for dv in dv_list:
            if dv.formula1 and "Lists" in dv.formula1:
                for sqref in str(dv.sqref).split():
                    if "B" in sqref:
                        found = True
                        break
        assert found, "No data validation for Source (column B)"


# ---------------------------------------------------------------------------
# Color fill tests
# ---------------------------------------------------------------------------

class TestColorFills:
    def test_predicted_category_cells_have_fills(self, generated_wb):
        ws = generated_wb["Inquiries"]
        for row in range(2, 5):
            cell = ws.cell(row=row, column=9)
            assert cell.fill is not None and cell.fill.fill_type == "solid"

    def test_final_category_cells_have_fills(self, generated_wb):
        ws = generated_wb["Inquiries"]
        for row in range(2, 5):
            cell = ws.cell(row=row, column=10)
            assert cell.fill is not None and cell.fill.fill_type == "solid"

    def test_unclear_category_has_distinct_fill(self, generated_wb, config):
        ws = generated_wb["Inquiries"]
        unclear_color = config.color_map["Unclear"].lstrip("#").upper()
        # Find the Unclear row (r3 has ts=1705190400.0 which is smallest -> row 2)
        # Check that at least one predicted category cell has the Unclear color
        found = False
        for row in range(2, 5):
            cell = ws.cell(row=row, column=9)
            if cell.value == "Unclear":
                fill_color = cell.fill.fgColor.rgb if cell.fill.fgColor else None
                # fgColor.rgb may have alpha prefix (FF + hex)
                if fill_color and unclear_color in fill_color.upper():
                    found = True
        assert found, "No Unclear row with distinct fill color found"

    def test_category_color_matches_config(self, generated_wb, config):
        ws = generated_wb["Inquiries"]
        for row in range(2, 5):
            category = ws.cell(row=row, column=9).value
            if category and category in config.color_map:
                expected_color = config.color_map[category].lstrip("#").upper()
                cell_fill = ws.cell(row=row, column=9).fill
                if cell_fill and cell_fill.fgColor:
                    actual_rgb = cell_fill.fgColor.rgb.upper()  # may have FF prefix
                    assert expected_color in actual_rgb, (
                        f"Row {row}: category {category!r} expected color {expected_color} "
                        f"but got {actual_rgb}"
                    )
