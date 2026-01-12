# Redacting Documents

This guide covers the document redaction workflow in Tractor.

## Understanding Redaction Suggestions

When a document is uploaded, Tractor uses a Named Entity Recognition (NER) model to automatically identify potentially sensitive information. These suggestions appear in the Redaction Sidebar for you to review.

!!! info
    The accuracy of suggestions depends on the trained model. As more redactions are accepted and the model is retrained, suggestions should improve over time.

## Reviewing Redactions

Once a document has been processed, you can review it by clicking on the document in the case page.

The **Redaction Sidebar** displays all suggested redactions. For each suggestion, you can:

- **Accept** - Click the accept button to confirm the redaction. Use the dropdown arrow to accept as a different redaction type if needed.
- **Reject** - Click the reject button to dismiss the suggestion. You will be asked to provide a reason for rejection (this is for audit purposes, not used by the system).

## Redaction Types

Tractor currently supports the following redaction types:

| Type | Description |
|------|-------------|
| **Operational Data** | Internal operational information |
| **Third-Party PII** | Personally identifiable information belonging to third parties |
| **Data Subject Information** | Information relating to the data subject of the case |

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
