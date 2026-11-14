# Redacting Documents

This guide covers the document redaction workflow in Tractor.

## Understanding Redaction Suggestions

When a document is uploaded, Tractor automatically identifies potentially sensitive information using four models working together:

- A **trained model** (SpanCat) built from your organisation's accepted redactions. Once trained, this identifies both **Operational Data** and **Third-Party PII** tailored to your organisation's documents. Until training data has been collected and a model trained, this step is skipped.
- **GLiNER** — a zero-shot model that recognises common **Third-Party PII** such as names, organisations, addresses, and dates of birth. This works immediately without any training.
- **Presidio** — a pattern-based engine that detects structured **Third-Party PII** (phone numbers, email addresses, NHS numbers, postcodes, National Insurance numbers) and structured **Operational Data** (crime reference numbers, collar numbers).
- **Contextual AI (Gemma)** — a locally-hosted large language model that reads the document and reasons about what information would be disclosable given the broader context. This catches disclosures that pattern-matching alone may miss. Suggestions from this model are labelled **AI (Contextual)** in the sidebar.

Suggestions appear in the Redaction Sidebar for you to review.

!!! info
    The trained model takes priority over the others. As more redactions are accepted and the model is retrained, its suggestions will improve over time and better reflect your organisation's specific patterns.

### Data Subject Filtering

Tractor automatically excludes the **data subject's own name and date of birth** from redaction suggestions. Since the data subject's information should remain visible in disclosure documents, it will not appear as a suggested redaction.

If other text belongs to the data subject, mark it as **Data Subject Information**: use **Reject as Data Subject** on a suggestion, or highlight the text with the **DS Info** tool. Data Subject Information is disclosed rather than redacted, and it automatically propagates to matching text across all documents in the case.

## Reviewing Redactions

Once a document has been processed, you can review it by clicking on the document in the case page.

The **Redaction Sidebar** displays all suggested redactions grouped by status (Pending, Accepted, Rejected). Each suggestion shows a badge indicating its source:

| Badge               | Meaning                                                    |
|---------------------|------------------------------------------------------------|
| **AI**              | Suggested by one of the pattern-matching or NER models     |
| **AI (Contextual)** | Suggested by the contextual AI (Gemma) model               |
| **User**            | Created manually by a reviewer                             |

For each suggestion, you can:

- **Accept** - Click the accept button to confirm the redaction. Use the dropdown arrow to accept it as a different redaction type instead. On a **Data Subject Information** suggestion, choose **Accept as Third-Party PII** when the text is someone else's personal data, so it is withheld rather than disclosed.
- **Accept with an exemption** - On an **Operational Data** suggestion, the same dropdown lists your organisation's exemptions below the types. Type to search, then click one to accept the suggestion withheld under that exemption. See [Exemptions](#exemptions) below.
- **Reject** - Click the reject button to dismiss the suggestion. The text will be disclosed. No reason is needed, and the suggestion moves straight to Rejected.
- **Reject as Data Subject** - In the dropdown on the Reject button. Use this when the suggested text is the data subject's own information: it is reclassified as **Data Subject Information**, so it stays visible in the disclosure, and it propagates to matching text across every document in the case. A Data Subject Information suggestion has no Reject dropdown, since it already is one; its plain **Reject** discloses the text without propagating it.

### Exemptions

An exemption is the stated basis for withholding **Operational Data**, chosen from a list your organisation maintains (see [Settings](settings.md#exemption-templates)). Only Operational Data carries one: Third-Party PII is withheld by default and needs no basis, and Data Subject Information is disclosed. If a Third-Party PII or Data Subject Information suggestion is really operational, accept it as Operational Data first, then give it an exemption on its card.

- **Choosing one** - Pick it from the Accept dropdown on an Operational Data suggestion. On a merged or grouped item it applies to every part.
- **Changing or clearing one** - Every accepted Operational Data card, including manual redactions, shows its exemption as a button, or **Add exemption** when it has none. Click it to pick another exemption, or **Clear exemption** to keep withholding the text with no stated basis. The redaction stays accepted either way.
- **What clears one** - Rejecting a redaction, returning it to pending, or changing its type away from Operational Data removes its exemption.
- **Across the case** - When a new document arrives, text accepted in every other document of the case is accepted again. It keeps an exemption only if all those earlier accepts used the same one.

Once a case has been disclosed, exemptions are locked along with every other decision until an Internal Review is opened.

### Merged Redactions

Adjacent spans of the same type that appear close together in the text are automatically **merged** into a single item in the sidebar. For example, if "John" and "Smith" are detected separately, they will appear as one combined "John Smith" item.

If you need to review or action the individual spans separately, click the **split** icon on a merged item to expand it back into its component parts.

### Bulk Actions

Items that share the same text and redaction type are grouped together in the sidebar. You can act on the entire group at once:

- **Accept All** — accepts every item in the group in one click. Its dropdown offers the same types, and on an Operational Data group the same exemptions, as a single suggestion does, plus **Accept all in case**
- **Reject All** — rejects all items in the group in one click. Its dropdown offers **Reject as Data Subject** (except on a Data Subject Information group) and **Reject all in case**, which asks you to confirm before disclosing the text in every document

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
    - `disclosure/` - Documents with redactions applied for disclosure (PDF)

The appearance of the disclosure PDF is controlled by the **Disclosure style** setting on the Settings page. With the default **Black bars** style, redacted text is replaced with solid black rectangles. With the **Remove text** style, redacted content is removed and replaced with `[...]` markers where appropriate, producing a less visually striking document for applicants.

!!! note
    The in-browser document preview always shows colour-highlighted redactions regardless of the disclosure style setting. To see the removal style in effect, you must generate and download a disclosure package.

### After Disclosure

Once a disclosure package has been generated, the case is **disclosed and locked** — its redactions become read-only so the record of what was disclosed is preserved. Every disclosure package is kept in the case's **Disclosure History**, where it can be downloaded again at any time.

If the disclosure is later challenged, you can open an **internal review** to make targeted changes and re-disclose. See [Internal Review](internal-review.md).
