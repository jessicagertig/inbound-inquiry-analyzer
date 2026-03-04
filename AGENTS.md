# Agents Guide

## Environment Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Running Tests

```bash
.venv/bin/pytest tests/ -q          # all tests (no API key required)
.venv/bin/pytest tests/test_claude_classifier.py -v  # Claude classifier only
```

## Running the CLI

```bash
# Keyword-only mode (no API key needed)
.venv/bin/inbound-inquiry-analyzer --keyword-only input.json

# Claude mode (requires ANTHROPIC_API_KEY in environment or .env file)
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=...
.venv/bin/inbound-inquiry-analyzer input.json -o output.xlsx
```

## Project Structure

- `src/inbound_inquiry_analyzer/` — main package
  - `cli.py` — CLI entry point, wires all modules together
  - `claude_classifier.py` — Claude-powered classification with keyword fallback
  - `classifier.py` — keyword-based classification (offline, deterministic)
  - `xlsx_writer.py` — XLSX workbook generation
  - `config.py` — YAML config loader
  - `normalizer.py` — record normalization
  - `parser.py` — JSON/CSV input parsing
- `tests/` — pytest test suite (126 tests, all mocked)
- `config/categories.yaml` — category names, colors, and source options
- `.env.example` — template for API key setup
