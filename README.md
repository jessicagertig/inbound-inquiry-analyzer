# Inbound Inquiry Analyzer

Classify inbound customer inquiries and export them to a formatted Excel workbook. Uses Claude AI for classification, with a keyword-based fallback for offline or API-key-free use.

## Installation

### Requirements

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/) (required for Claude mode; optional with `--keyword-only`)

### Steps

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package with all dependencies
pip install -e ".[dev]"
```

### API Key Setup

Copy the provided template and add your key:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

`.env.example` contents:

```
ANTHROPIC_API_KEY=your_api_key_here
```

The `.env` file is gitignored and must never be committed. The tool loads it automatically at startup using `python-dotenv`. You can also export the key directly:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## CLI Usage

```
inbound-inquiry-analyzer [FILE ...] [-o OUTPUT] [-c CONFIG] [--keyword-only]
```

### Arguments

| Argument | Description | Default |
|---|---|---|
| `FILE ...` | One or more input files (JSON or CSV). Reads from stdin if omitted. | stdin |
| `-o OUTPUT` | Output XLSX file path. | `inquiries_categorized.xlsx` |
| `-c CONFIG` | Path to a custom `categories.yaml` config file. | `config/categories.yaml` |
| `--keyword-only` | Skip Claude entirely; use only keyword-based classification. Useful offline or when no API key is available. | off |

### Examples

```bash
# Classify a single file using Claude (requires ANTHROPIC_API_KEY)
inbound-inquiry-analyzer inquiries.json

# Classify and write output to a specific path
inbound-inquiry-analyzer inquiries.json -o results/output.xlsx

# Classify multiple files at once
inbound-inquiry-analyzer jan.json feb.json mar.json -o q1.xlsx

# Use a custom category config
inbound-inquiry-analyzer inquiries.json -c config/my_categories.yaml

# Keyword-only mode (no API key required)
inbound-inquiry-analyzer --keyword-only inquiries.json

# Read from stdin (pipe)
cat inquiries.json | inbound-inquiry-analyzer -o output.xlsx

# Stdin with keyword-only
cat inquiries.json | inbound-inquiry-analyzer --keyword-only
```

### Classification Modes

**Claude mode (default):** All records are sent to Claude in a single API call. Claude returns a category for each inquiry using the allowed categories from your config. If Claude's response cannot be parsed, or Claude returns an unknown category for a specific record, that record falls back to keyword classification individually. A summary is printed to stderr:

```
Classification: 47 via claude, 3 via keyword
Processed 50 inquiries -> inquiries_categorized.xlsx
```

**Keyword-only mode (`--keyword-only`):** Classification is performed entirely offline by matching keywords in the subject and message body against each category name. No API calls are made. Useful for testing, CI environments, or when the API key is unavailable.

**Automatic fallback:** If `ANTHROPIC_API_KEY` is not set and `--keyword-only` is not passed, the tool warns and falls back to keyword mode:

```
Warning: ANTHROPIC_API_KEY is not set. Falling back to keyword classification.
Pass --keyword-only to suppress this warning.
```

---

## Input Format

The tool auto-detects the input format from the field names in the first record. Two JSON shapes are supported, plus CSV equivalents.

### Intercom JSON

Detected by the presence of the fields `first_message` and `contact_email`.

```json
[
  {
    "id": "conv_001",
    "state": "open",
    "subject": "Can't log in to my account",
    "first_message": "<p>I've been trying to log in for the past hour...</p>",
    "contact_email": "user@example.com",
    "contact_name": "Jane Smith",
    "created_at": 1706745600
  }
]
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Used as the inquiry ID |
| `subject` | string | yes | Email subject line |
| `first_message` | string | yes | Message body (may contain HTML; stripped during normalization) |
| `contact_email` | string | yes | Sender email address |
| `contact_name` | string | no | Sender display name |
| `state` | string | no | Conversation state (e.g. `"open"`) |
| `created_at` | integer | yes | Unix timestamp (seconds) |

### In-App Contact Form JSON

Detected by the presence of the fields `body` and `reply_to_email`.

```json
[
  {
    "id": "form_042",
    "subject": "Question about pricing",
    "body": "Hi, I'd like to know the difference between the Starter and Pro plans.",
    "reply_to_email": "customer@example.com",
    "created_at": "2024-02-01"
  }
]
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Used as the inquiry ID |
| `subject` | string | yes | Form subject |
| `body` | string | yes | Message body (plain text) |
| `reply_to_email` | string | yes | Sender email address |
| `created_at` | string | yes | Date in `YYYY-MM-DD` format |

### CSV

CSV files are also supported. Column names must match the JSON field names for the appropriate format (Intercom or contact form). The format is detected from the column headers.

```bash
inbound-inquiry-analyzer inquiries.csv
```

### Mixing Formats

When passing multiple files, each file is parsed independently using its own format detection. You can mix Intercom and contact form files in a single invocation:

```bash
inbound-inquiry-analyzer intercom_export.json contactform_export.csv -o combined.xlsx
```

---

## Output Format

The tool writes an Excel workbook (`.xlsx`) with two sheets.

### `Inquiries` Sheet

The main data sheet, sorted by received timestamp ascending. It contains 11 columns:

| # | Column | Description |
|---|---|---|
| A | **Inquiry ID** | Original ID from the source system |
| B | **Source** | Source system (populated from `sources` in config; has a dropdown) |
| C | **Received At (YYYY-MM-DD)** | Date portion of the received timestamp |
| D | **Received At (Timestamp)** | Full ISO-like timestamp string |
| E | **From Name** | Sender's display name |
| F | **From Email** | Sender's email address |
| G | **Subject** | Inquiry subject line |
| H | **Message Body** | Full message text (text-wrapped) |
| I | **Predicted Category** | Category assigned by the classifier (color-coded, read-only reference) |
| J | **Final Category** | Editable category with a dropdown for manual correction (color-coded) |
| K | **Notes** | Free-text notes field (blank by default) |

**Formatting:**
- Header row is blue (`#4472C4`) with white bold text.
- Header row is frozen (rows scroll, header stays).
- Auto-filter is enabled on the header row.
- **Predicted Category** and **Final Category** cells are color-filled based on the category's configured color (see [Classification Config](#classification-config)). Non-configured categories receive a light grey fill (`#E0E0E0`). Note: fills are static — they do not update automatically when you change **Final Category** in Excel.

### `Lists` Sheet (hidden)

A hidden helper sheet used for data validation. It is not intended for direct editing.

| Column A | Column B |
|---|---|
| Category names (from config + any extra predicted categories) | Source names (from config) |

**Final Category** (column J) and **Source** (column B) have Excel dropdown validation referencing this sheet. Dropdowns extend 100 rows beyond the last data row so you can add rows manually.

---

## Classification Config

Category names, colors, and source options are defined in `config/categories.yaml`.

### Schema

```yaml
categories:
  - name: "Category Name"   # string, required — must be unique
    color: "#RRGGBB"        # hex color string, required — used for cell fills

sources:
  - "Source Name"           # list of strings, required
```

### Default Config

```yaml
categories:
  - name: "Issue with login"
    color: "#FFD700"
  - name: "Inquiry about plan or pricing"
    color: "#90EE90"
  - name: "Request for data deletion"
    color: "#FFB6C1"
  - name: "Wrong email address (not intended for Polymer)"
    color: "#ADD8E6"
  - name: "Advertising or solicitation"
    color: "#D3D3D3"
  - name: "Knowledge base help"
    color: "#DDA0DD"
  - name: "Feature help"
    color: "#87CEEB"
  - name: "Migration"
    color: "#F0E68C"
  - name: "Refund request"
    color: "#FFA07A"
  - name: "Other"
    color: "#E0E0E0"
  - name: "Unclear"
    color: "#FF4500"

sources:
  - "Intercom"
  - "In-app contact form"
  - "Discord"
  - "Direct email inquiry"
  - "LinkedIn message"
```

### Notes

- **Always include `"Unclear"`** as the last category. Both Claude and keyword classifiers fall back to `"Unclear"` when no better match is found.
- **Category names are exact-match**: Claude is instructed to return category names verbatim. Spaces, capitalization, and punctuation must match exactly between the config and what Claude returns.
- **Non-configured categories**: If Claude returns a category not in the config (rare edge case), it is appended to the `Lists` sheet and the dropdown, and receives the default grey fill (`#E0E0E0`). This ensures the workbook is always consistent.
- To use a different config file, pass `-c path/to/config.yaml` to the CLI.

---

## Running Tests

All tests are mocked — no API key is required:

```bash
.venv/bin/pytest tests/ -q
```

To run a specific test module:

```bash
.venv/bin/pytest tests/test_claude_classifier.py -v
.venv/bin/pytest tests/test_cli.py -v
```
