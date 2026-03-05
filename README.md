# Inbound Inquiry Analyzer

A CLI tool that classifies inbound customer inquiries from Intercom exports and contact form submissions, then outputs a formatted XLSX workbook for review.

## Features

- **Auto-detects input format** — Intercom JSON exports and contact form JSON/CSV
- **Dual classification modes** — Claude API (claude-sonnet-4-6) with automatic keyword fallback
- **Formatted XLSX output** — color-coded rows, dropdown for manual re-categorization, auto-filters, frozen headers
- **Configurable categories** — define categories and colors in a simple YAML file
- **Multiple file support** — combine different formats in a single run

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/jessicagertig/inbound-inquiry-analyzer.git
cd inbound-inquiry-analyzer
pip install -e '.[dev]'
```

## Configuration

To enable Claude-powered classification, copy `.env.example` to `.env` and add your Anthropic API key:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-...
```

Without an API key the tool falls back to keyword-based classification automatically.

## Usage

```bash
# Classify a single file
inbound-inquiry-analyzer export.json

# Multiple files, custom output
inbound-inquiry-analyzer jan.json feb.csv -o q1_inquiries.xlsx

# Keyword-only mode (no API key needed)
inbound-inquiry-analyzer export.json --keyword-only

# Pipe from stdin
cat export.json | inbound-inquiry-analyzer -o out.xlsx

# Custom category config
inbound-inquiry-analyzer export.json -c my_categories.yaml
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `FILE ...` | stdin | One or more input files (JSON or CSV) |
| `-o`, `--output` | `inquiries_categorized.xlsx` | Output XLSX path |
| `-c`, `--config` | `config/categories.yaml` | Categories YAML config path |
| `--keyword-only` | off | Force keyword classification, skip Claude |

## Input Formats

The tool auto-detects the format based on field signatures.

**Intercom export (JSON):** Records with `first_message` and `contact_email` fields.

**Contact form (JSON or CSV):** Records with `reply_to_email` and `body` fields.

See [docs/input-formats.md](docs/input-formats.md) for field details and examples.

## Output

The XLSX workbook contains:

- **Inquiries sheet** — one row per inquiry with Date, Source, From Name, From Email, Subject, Message Body, Predicted Category, Final Category (editable dropdown), and Notes
- **Lists sheet** (hidden) — powers the Final Category dropdown validation

Rows are color-coded by predicted category and sorted oldest-first.

## Classification

The keyword classifier uses 9 priority-ordered rules (first match wins): data deletion, wrong email, advertising, login issues, refund requests, plan/pricing inquiries, migration, knowledge base help, and feature help. Unmatched inquiries are marked **Unclear**.

Claude classification sends each inquiry to the API with the full category list. It may suggest new categories not in the config — these are added to the dropdown for the current run but not persisted to the YAML file.

Categories can be customized by editing `config/categories.yaml`. See [docs/classification-config.md](docs/classification-config.md) for details.

## Running Tests

```bash
pytest
```
