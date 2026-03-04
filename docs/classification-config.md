# Classification Configuration

## Categories file

Categories are defined in `config/categories.yaml`. This file controls which categories appear in the XLSX dropdown and what background color each row gets.

```yaml
categories:
  - name: Issue with login
    color: "#FFD700"
  - name: Refund request
    color: "#FFA07A"
  - name: Other          # manual-only: no classifier rule
    color: "#E0E0E0"
  - name: Unclear        # automatic fallback when no rule matches
    color: "#FF4500"

sources:
  - Intercom
  - In-app contact form
```

- **`name`** — Category label shown in the XLSX dropdown and Predicted Category column.
- **`color`** — Hex color applied to the row fill in the output workbook.

## Keyword classifier rules

The keyword classifier uses 9 priority-ordered rules (first match wins). A record's subject and message body are searched case-insensitively.

| Priority | Category |
|----------|----------|
| 1 | Request for data deletion |
| 2 | Wrong email address (not intended for Polymer) |
| 3 | Advertising or solicitation |
| 4 | Issue with login |
| 5 | Refund request |
| 6 | Inquiry about plan or pricing |
| 7 | Migration |
| 8 | Knowledge base help |
| 9 | Feature help |

When no rule matches, the classifier returns **Unclear**.

> **Important:** "Refund request" (rule 5) must appear before "Inquiry about plan or pricing" (rule 6) because the keyword `subscription` would otherwise falsely match billing-related refund messages.

> **Important:** The **"Other"** category has no classifier rule. It exists in `categories.yaml` only so users can manually re-categorize rows in the Final Category dropdown.

## Claude classification

When `ANTHROPIC_API_KEY` is set and `--keyword-only` is not passed, the tool sends each inquiry to Claude (claude-sonnet-4-6) along with the full category list. Claude returns exactly one category name.

Claude may return a category not in `categories.yaml` when no existing option fits. Such new categories are:
- Added to the XLSX Lists sheet and Final Category dropdown for the current run
- Assigned a default color of `#E0E0E0`
- **Not** persisted to `categories.yaml`

## Adding or editing categories

Edit `config/categories.yaml` directly. Use any valid CSS hex color. Re-run the tool to pick up changes.
