# Settings

The Settings page allows administrators to configure Tractor for your organisation.

## Document Export Settings

These settings control the appearance of every PDF produced by an export. They are applied system-wide — there are no per-case or per-document overrides.

Navigate to **Settings** and find the **Document Export Settings** card.

### Header

Text entered in the **Header text** field appears centred in the top margin of every exported page. Leave blank to suppress the header entirely.

### Footer

Text entered in the **Footer text** field appears centred in the bottom margin of every exported page. Leave blank to suppress the footer entirely.

### Watermark

Text entered in the **Watermark text** field is rendered diagonally across the centre of every page in a large, semi-transparent grey font (e.g. `DRAFT`, `SAR`, `RESTRICTED`).

Enable **Include case reference in watermark** to append the case reference to the watermark text automatically (e.g. `SAR 2025-001`). This toggle is disabled when the watermark text field is empty.

### Page Numbers

Enable **Show page numbers** to add "Page X of Y" below the footer text on every page. If no footer text is set, the page number appears on its own.

### Export Font

The **Export font** dropdown controls the typeface used for all body text in exported PDFs. Choose from the following options:

| Option          | Font                   |
|-----------------|------------------------|
| Arial           | Arial, sans-serif      |
| Times New Roman | Times New Roman, serif |
| Courier New     | Courier New, monospace |
| Georgia         | Georgia, serif         |
| Verdana         | Verdana, sans-serif    |

All fonts in this list are cross-platform web-safe fonts that render consistently on Linux servers without any additional font installation. The default is **Arial**.

### Saving

Click **Save** to apply changes. The new settings take effect on the next export — previously generated ZIP packages are not retroactively updated.

!!! note
    These settings are only visible and editable by administrators.

---

## Contextual AI Prompt

The contextual AI (Gemma) model uses a system prompt to understand what kind of information it should identify as potentially disclosable. This prompt can be customised to reflect your organisation's specific disclosure requirements.

Navigate to **Settings** and find the **Contextual AI Prompt** card, then click **Configure**.

The dialog shows a text area containing the current system prompt. Edit it to change the instructions given to the AI on every document it analyses.

### Reset to Default

Click **Reset to default** below the text area to restore the original built-in prompt without saving. This only changes the text in the editor — click **Save** to apply it.

### Saving

Click **Save** to apply the new prompt. The change takes effect on the next document processed — documents already in the queue or previously processed are not affected.

!!! note
    This setting is only visible and editable by administrators.

!!! note
    The Contextual AI Prompt card only appears if Ollama is enabled in your deployment (`OLLAMA_ENABLED=True`). If the card is not visible, the contextual AI stage is disabled.

---

## Custom Recognizers

Custom recognizers let you define organisation-specific patterns that are applied automatically during document processing, alongside the built-in extractors. Any text matching an active recognizer is surfaced as a redaction suggestion in the review panel.

Navigate to **Settings** and find the **Custom Recognizers** card, then click **Manage**.

### Types of recognizer

| Type | When to use |
|------|-------------|
| **Regex patterns** | Reference formats that follow a predictable structure (e.g. a bespoke crime-numbering scheme or a local identifier format). Each pattern has a name, a regular expression, and a confidence score. |
| **Deny list** | Specific literal strings that must always be flagged (e.g. known officer names or project code-words that do not follow a pattern). |

A single recognizer can only be one type. Choose **Regex patterns** or **Deny list** from the recognizer type dropdown when creating it.

### Entity type

Each recognizer is assigned to one of two categories:

| Entity type | Effect |
|-------------|--------|
| **Third-Party PII** | Matches are treated as third-party personal information, equivalent to an email address or NHS number detected by the built-in extractor. |
| **Operational Data** | Matches are treated as operational references, equivalent to crime reference numbers or collar numbers. |

### Adding a recognizer

1. Click **Add recognizer**.
2. Enter a **name** (required) and an optional **description**.
3. Select the **entity type** and **recognizer type**.
4. Add one or more pattern rows (for regex recognizers) or term rows (for deny-list recognizers).
5. For regex recognizers, use the **Regex tester** widget at the bottom of the form to validate your pattern against sample text before saving.
6. Click **Save**.

### Regex tester

The regex tester sends your pattern and sample text to the server and highlights any matches in real time (with a short debounce delay). If the pattern is invalid, an error message appears inline. Patterns are evaluated server-side — the tester does not apply the regex locally.

### Editing and disabling

- **Edit** — Click the pencil icon next to a recognizer to update its name, description, patterns, or terms.
- **Enable / disable** — Toggle the switch in the **Active** column to suspend a recognizer without deleting it. Disabled recognizers are ignored during extraction; re-enabling takes effect on the next document processed.
- **Delete** — Click the delete icon and confirm the prompt. Deletion is permanent.

### How matches appear

Custom recognizer matches appear in the review panel alongside built-in detections and participate in the standard deduplication priority order (SpanCat > GLiNER > Presidio / custom > Gemma). They are labelled by entity type in the same way as built-in results.

Changes to custom recognizers take effect on the next document processed — documents already reviewed are not retroactively updated.

---

## Exemption Templates

Exemption templates are pre-configured rejection reasons that reviewers can select when rejecting a redaction suggestion. Rather than typing a reason from scratch each time, reviewers can pick from a searchable list of standard exemptions (e.g. "S.40 - Personal Information", "S.42 - Legal Privilege").

### Managing Templates

Navigate to **Settings** and find the **Exemption Templates** card.

- **Adding a template** — Click **Add**, enter a name (required) and an optional description, then click **Save**.
- **Deleting a template** — Click the delete icon next to a template and confirm the prompt.

!!! note
    Only active templates appear in the rejection dropdown. Templates can also be managed directly through the Django Admin at `/admin/cases/exemptiontemplate/`, where they can be marked as inactive to hide them from reviewers without deleting them.

### How Reviewers Use Exemptions

When reviewing a document, the dropdown arrow on the **Reject** button opens a searchable list of configured exemptions. Reviewers can type to filter the list and click an exemption to reject the suggestion immediately with that reason recorded.

For one-off reasons that do not fit an existing template, reviewers can still click **Reject** directly to open the free-text dialog.

---

## API Keys

!!! note
    This section is only visible and accessible to administrators.

API keys allow external services to create cases programmatically via the REST API. Each key authenticates as a system service account so cases have a stable `created_by` attribution regardless of staff changes.

### Managing API Keys

Navigate to **Settings** and find the **API Keys** card.

- **Generating a key** — Click **Manage**, then **Generate Key**. Enter a description that identifies the integration (e.g. `Case management integration`), then click **Generate**. The key is displayed **once** immediately after creation — copy it now, as it cannot be retrieved again.
- **Revoking a key** — Click the delete icon next to a key and confirm the prompt. Revocation is immediate; any integration using that key will receive `401 Unauthorized` responses.

### Using an API Key

Include the key in the `Authorization` header of your HTTP requests:

```
Authorization: Api-Key <your-key>
```

**Example — creating a case:**

```bash
curl -X POST https://your-tractor-instance/api/cases \
  -H "Authorization: Api-Key <your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "case_reference": "2025-0001",
    "data_subject_name": "Jane Smith",
    "data_subject_dob": "1985-06-15"
  }'
```

!!! warning
    Treat API keys like passwords. Store them in your integration's secret store (e.g. a CI/CD secrets vault or environment variable), not in source code or plain text files.

API keys can also be managed directly through the Django Admin at `/admin/authentication/apikey/`.
