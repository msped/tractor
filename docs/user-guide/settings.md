# Settings

The Settings page allows administrators to configure Tractor for your organisation.

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
