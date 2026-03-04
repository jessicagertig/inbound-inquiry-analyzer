# Input Format Specification

The tool auto-detects the input format (Intercom or contact form) based on field signatures.

## Intercom export (JSON)

A JSON array of conversation objects. The format is detected when records contain both `first_message` and `contact_email`.

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Conversation identifier |
| `created_at` | integer | Unix timestamp (UTC) of when the conversation was created |
| `subject` | string | Conversation subject line |
| `first_message` | string | HTML body of the first inbound message |
| `contact_email` | string | Email address of the contact |
| `contact_name` | string | Display name of the contact |

### Example

```json
[
  {
    "id": "conv_123",
    "created_at": 1700000000,
    "subject": "I cannot log in",
    "first_message": "<p>I forgot my password and the reset email never arrives.</p>",
    "contact_email": "alice@example.com",
    "contact_name": "Alice Smith"
  }
]
```

> **Note:** The `first_message` field contains HTML which is preserved as-is in the output XLSX.

## Contact form export (JSON or CSV)

Detected when records contain `reply_to_email` and `body`. CSV files are detected by `.csv` extension or when the content does not start with `{` or `[`.

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `reply_to_email` | string | Sender's email address |
| `subject` | string | Subject line |
| `body` | string | Plain-text message body |
| `date` | string | Submission date in `YYYY-MM-DD` format |

### CSV example

```csv
reply_to_email,subject,body,date
bob@example.com,Refund inquiry,I would like a refund for my last payment.,2024-03-15
```

### JSON example

```json
[
  {
    "reply_to_email": "bob@example.com",
    "subject": "Refund inquiry",
    "body": "I would like a refund for my last payment.",
    "date": "2024-03-15"
  }
]
```

## Mixed inputs

Multiple files of different formats can be passed in a single invocation:

```bash
inbound-inquiry-analyzer intercom.json contact_forms.csv -o combined.xlsx
```
