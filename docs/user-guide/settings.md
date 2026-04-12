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
