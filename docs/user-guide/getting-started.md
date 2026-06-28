# Getting Started

This guide will help you get started with Tractor.

## Prerequisites

- **Browser**: Tractor should work on any modern browser (Chrome, Firefox, Edge, Safari)
- **Account**: You will need an account to access Tractor. Either:

  - An administrator creates an account for you, or
  - If your organisation uses Microsoft Entra ID, you will need to be granted permissions to the application in your tenant

## Logging In

Tractor supports two authentication methods:

### Username and Password

If an administrator has created an account for you, enter your username and password on the login page.

### Microsoft Entra ID (SSO)

If your organisation has configured Microsoft Entra ID integration, a "Sign in with Microsoft" option will appear on the login page. Click this to authenticate with your organisation's Microsoft account.

!!! note
    The Microsoft sign-in option only appears if it has been configured for your deployment.

## Creating Your First Case

To create your first case, you can click '+ New Case' on the sidebar to the left handside.

You will requested to provide information relating to the case:

- Case reference from your organisation.
- Data Subject Name
- Data Subject Date of Birth

The case reference can be up to 6 characters (alphanumeric), however can be changed to suit to your needs by modifying `case_reference` field on `cases/models.py` in the `Cases class`.

Once these fields are complete, you can click the button 'Create Case' which will redirect you the case page.

## Adding Documents

After navigating to the cases page of the case you would like to add documents to, underneath the Case information you will see a section for the case documents.

To add a new document, click 'Add Document' on the top right of this section. A modal will open with two tabs:

### Upload File

Drag and drop files into the area, or click to open the file browser. Supported formats are DOCX and PDF.

Once files are selected they will appear below the drop area, where you can rename each file before it is saved. Click 'Upload' to submit — the modal will close and the document will appear under 'Case Documents' with the status of 'Processing'.

### Paste Text (Alpha)

!!! warning
    This feature is in alpha. Behaviour when pasting from certain systems may be unpredictable.

If you have text you want to analyse without a file, switch to the 'Paste Text' tab. Enter a document name, paste the content into the text area, and click 'Create'.

The content is processed through the same NER pipeline as uploaded documents. Note that **table formatting is not preserved** — if your source document contains tables, the text within them will be extracted as plain text only.

## Next Steps

Once you've created a case and uploaded documents, learn how to [redact documents](redaction.md).
