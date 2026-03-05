# Installation

## Requirements

- Python 3.10 or later (3.11 tested on macOS)
- pip

## Install for development

```bash
git clone <repo-url>
cd inbound-inquiry-analyzer
pip install -e '.[dev]'
```

This installs the package in editable mode along with development dependencies (pytest, pre-commit).

## Environment configuration

Copy `.env.example` to `.env` and add your Anthropic API key if you want Claude-powered classification:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-...
```

The `.env` file is listed in `.gitignore` and should never be committed.

When `ANTHROPIC_API_KEY` is absent the tool automatically falls back to keyword-based classification — no error is raised.

## Verify installation

```bash
inbound-inquiry-analyzer --help
```

Or:

```bash
python -m inbound_inquiry_analyzer --help
```
