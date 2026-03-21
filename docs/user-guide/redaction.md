# Redacting Documents

This guide covers the document redaction workflow in Tractor.

## Understanding Redaction Suggestions

When a document is uploaded, Tractor automatically identifies potentially sensitive information using three models working together:

- A **trained model** (SpanCat) built from your organisation's accepted redactions. Once trained, this identifies both **Operational Data** and **Third-Party PII** tailored to your organisation's documents. Until training data has been collected and a model trained, this step is skipped.
- **GLiNER** — a zero-shot model that recognises common **Third-Party PII** such as names, organisations, addresses, and dates of birth. This works immediately without any training.
- **Presidio** — a pattern-based engine that detects structured **Third-Party PII** (phone numbers, email addresses, NHS numbers, postcodes, National Insurance numbers) and structured **Operational Data** (crime reference numbers, collar numbers).

Suggestions appear in the Redaction Sidebar for you to review.

!!! info
    The trained model takes priority over the other two. As more redactions are accepted and the model is retrained, its suggestions will improve over time and better reflect your organisation's specific patterns.

### Data Subject Filtering

Tractor automatically excludes the **data subject's own name and date of birth** from redaction suggestions. Since the data subject's information should remain visible in disclosure documents, it will not appear as a suggested redaction.

If you need to mark the data subject's information for redaction, you can still create manual redactions using the **Data Subject Information** type. These will automatically propagate to matching text across all documents in the case.

## Reviewing Redactions

Once a document has been processed, you can review it by clicking on the document in the case page.

The **Redaction Sidebar** displays all suggested redactions grouped by status (Pending, Accepted, Rejected). For each suggestion, you can:

- **Accept** - Click the accept button to confirm the redaction. Use the dropdown arrow to accept as a different redaction type if needed.
- **Reject** - Click the reject button to dismiss the suggestion. You will be asked to provide a reason for rejection (this is for audit purposes).
- **Reject with exemption** - Click the dropdown arrow on the Reject button to select a pre-configured exemption reason (e.g. "S.40 - Personal Information"). You can type to search the list. Selecting an exemption rejects the suggestion immediately without opening the dialog.

### Merged Redactions

Adjacent spans of the same type that appear close together in the text are automatically **merged** into a single item in the sidebar. For example, if "John" and "Smith" are detected separately, they will appear as one combined "John Smith" item.

If you need to review or action the individual spans separately, click the **split** icon on a merged item to expand it back into its component parts.

### Bulk Actions

Items that share the same text and redaction type are grouped together in the sidebar. You can act on the entire group at once:

- **Accept All** — accepts every item in the group in one click
- **Reject All** — opens the rejection reason dialog and rejects all items in the group

Individual items within a group can still be actioned separately by expanding the group.

## Manual Redactions

If the AI has missed something, or you need to redact text that falls outside the automatic suggestions, you can create manual redactions yourself. There are two ways to do this.

### Highlight Tool

The Redaction Sidebar contains three colour-coded buttons at the top — one for each redaction type:

| Button       | Type                     |
|--------------|--------------------------|
| **PII**      | Third-Party PII          |
| **Op. Data** | Operational Data         |
| **DS Info**  | Data Subject Information |

Click a button to activate that type as your active highlight tool. The button will appear bold to indicate it is active. Then select any text in the document — the redaction is applied immediately in that type's colour with no extra steps.

- Click the active button again, or press **Escape**, to deactivate the tool.
- When a tool is active, selecting text that already contains AI suggestions will **accept** those suggestions and apply the chosen type, creating new redactions for any uncovered gaps in your selection.

### Popover (Select and Choose)

If no highlight tool is active, selecting text will open a small popover. Choose the redaction type from the popover to create the redaction.

This method is useful when you want to consciously pick the type for each individual piece of text rather than painting with a pre-selected colour.

## Redaction Types

Tractor currently supports the following redaction types:

| Type                         | Description                                                    |
|------------------------------|----------------------------------------------------------------|
| **Operational Data**         | Internal operational information                               |
| **Third-Party PII**          | Personally identifiable information belonging to third parties |
| **Data Subject Information** | Information relating to the data subject of the case           |

!!! note
    Custom redaction types are not currently supported. The available types are defined in `cases/models.py`.

## Adding Context

When removing data would cause the reader to lose important context, you can add replacement text. This context will appear in brackets in the final disclosure document.

For example, redacting a name like "John Smith" could be replaced with context like "[Name of witness]" to help readers understand what was removed.

## Completing a Document

Once all redaction suggestions have been either accepted or rejected, the **"Mark as Complete"** button will become active. Click this to mark the document as completed.

You cannot mark a document as complete until all suggestions have been reviewed.

## Exporting a Case

Once **all documents** in a case have been marked as complete:

1. Navigate to the case page
2. The **"Generate Disclosure Package"** button will become active
3. Click the button to start generating the export (this runs in the background)
4. Once complete, the button will change to **"Download Package"**
5. Click to download a ZIP file containing:
    - `unedited/` - Original documents in their original format
    - `redacted/` - Documents with colour-highlighted redactions (PDF)
    - `disclosure/` - Documents with black-box redactions for disclosure (PDF)
