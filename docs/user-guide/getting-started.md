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

The case reference can be upto a 6 digit number, however can be changed to suit to your needs by modifying `case_reference` field on `cases/models.py` in the `Cases class`.

Once these fields are complete, you can click the button 'Create Case' which will redirect you the case page.

## Uploading Documents

After navigating to the cases page of the case you would like to upload documents to, underneath the Case information you will see a section for the case documents.

To upload new documents, click on 'Upload Document' on the top right of this section. A modal will open and give you the option to either drang and drop the files into the area, or clicking in the area will open the file browser to select files.

The current supported documents are docx and PDF.

Once either the files are selected, or files are dropped into the area, they will appear at the bottom of the modal where you are given the chance to name file on the system. The orginal file will always retain it's original file name.

Once you are happy, click 'Upload Document' and the modal will close where you will see it appear under 'Case Documents' with the status of 'Processing'.

## Next Steps

Once you've created a case and uploaded documents, learn how to [redact documents](redaction.md).
