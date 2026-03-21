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

| Option | Font |
|---|---|
| Arial | Arial, sans-serif |
| Times New Roman | Times New Roman, serif |
| Courier New | Courier New, monospace |
| Georgia | Georgia, serif |
| Verdana | Verdana, sans-serif |

All fonts in this list are cross-platform web-safe fonts that render consistently on Linux servers without any additional font installation. The default is **Arial**.

### Saving

Click **Save** to apply changes. The new settings take effect on the next export — previously generated ZIP packages are not retroactively updated.

!!! note
    These settings are only visible and editable by administrators.

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
