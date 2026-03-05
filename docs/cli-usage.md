# CLI Usage Reference

## Synopsis

```
inbound-inquiry-analyzer [FILE ...] [-o OUTPUT] [-c CONFIG] [--keyword-only]
```

## Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `FILE ...` | (stdin) | One or more input files (JSON or CSV). Reads from stdin when omitted and stdin is not a TTY. |
| `-o`, `--output` | `inquiries_categorized.xlsx` | Path for the output XLSX file. |
| `-c`, `--config` | `config/categories.yaml` | Path to the categories YAML config. |
| `--keyword-only` | off | Force keyword-based classification. Skips Claude even if `ANTHROPIC_API_KEY` is set. |

## Classification modes

By default the tool uses Claude classification (requires `ANTHROPIC_API_KEY`) and falls back to keyword classification per message on any API failure. The summary line printed to stderr reports the method used:

- `[classification: Claude API]` — all messages classified by Claude
- `[classification: keyword classifier]` — all messages classified by keywords
- `[classification: mixed (Claude + keyword fallback)]` — some by Claude, some by keywords

Use `--keyword-only` for offline use or reproducible runs.

## Examples

```bash
# Single file
inbound-inquiry-analyzer export.json

# Multiple files, custom output path
inbound-inquiry-analyzer jan.json feb.csv -o q1_inquiries.xlsx

# Pipe from stdin
cat export.json | inbound-inquiry-analyzer -o out.xlsx

# Keyword-only mode (no API key needed)
inbound-inquiry-analyzer export.json --keyword-only

# Custom config
inbound-inquiry-analyzer export.json -c my_categories.yaml
```
