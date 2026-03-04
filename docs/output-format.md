# Output Format Guide

The tool writes a single XLSX workbook with two sheets.

## Inquiries sheet

The main data sheet. Each row represents one inbound inquiry.

| Column | Description |
|--------|-------------|
| **Date** | Date the inquiry was received (YYYY-MM-DD) |
| **Source** | Where the inquiry came from (e.g. Intercom, In-app contact form) |
| **From Name** | Contact's display name |
| **From Email** | Contact's email address |
| **Subject** | Subject line of the message |
| **Message Body** | Full message body (HTML preserved for Intercom messages) |
| **Predicted Category** | Category assigned by the classifier (Claude or keyword) |
| **Final Category** | Editable dropdown — initially set to Predicted Category. Change this to your verified classification. |
| **Notes** | Blank column for analyst notes |

### Formatting

- **Header row**: bold, frozen so it stays visible while scrolling.
- **Data rows**: background color matches the Predicted Category color defined in `config/categories.yaml`. New categories from Claude get a neutral gray (`#E0E0E0`).
- **Auto-filter**: enabled on all columns.
- **Rows sorted** by timestamp (oldest first).

> **Note:** Row colors are static — they reflect the Predicted Category at generation time. Changing the Final Category dropdown in Excel will **not** update the row color.

## Lists sheet (hidden)

A helper sheet that powers the Final Category dropdown validation. It contains the full list of category names including any new categories Claude suggested during the current run.

The dropdown validation extends 100 rows beyond the last data row to support manual additions in Excel.
