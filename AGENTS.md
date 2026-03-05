# Agents Guide

## Running the tool

```bash
pip install -e '.[dev]'
inbound-inquiry-analyzer --help
```

Or:
```bash
python -m inbound_inquiry_analyzer [FILE ...] [-o OUTPUT] [-c CONFIG] [--keyword-only]
```

## Running tests

```bash
/opt/homebrew/bin/python3.11 -m pytest
```

(Use the full path — the system `python3` may not find the installed package.)

## Environment setup

Copy `.env.example` to `.env` and add `ANTHROPIC_API_KEY` for Claude classification. Without a key, the tool falls back to keyword classification automatically.

## Key notes

- Default output: `inquiries_categorized.xlsx`
- Default config: `config/categories.yaml`
- `--keyword-only` disables Claude even when API key is present
- New categories from Claude appear in the XLSX but are NOT written back to categories.yaml
