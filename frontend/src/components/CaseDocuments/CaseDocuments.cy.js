import React from 'react';
import { CaseDocuments } from './CaseDocuments';
import * as documentService from '@/services/documentService';

describe('<CaseDocuments />', () => {
  const caseId = 'case-1';
  const docs = [
    {
      id: 'doc-1',
      filename: 'document_alpha.pdf',
      file_type: 'pdf',
      uploaded_at: '2024-05-20T10:00:00Z',
      status: 'Processing'
    },
    {
      id: 'doc-2',
      filename: 'document_beta.docx',
      file_type: 'docx',
      uploaded_at_at: '2024-05-21T12:30:00Z',
      status: 'Ready for Review'
    },
    {
      id: 'doc-3',
      filename: 'document_gamma.pdf',
      file_type: 'pdf',
      uploaded_at: '2024-05-22T15:45:00Z',
      status: 'Error'
    }
  ];

  const mountOpts = { mockSession: { user: { id: '1', name: 'Test User', email: 'test@example.com' }, session: { token: 'fake-token', userId: '1' } } };

  it('renders provided documents', () => {
    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={false} />,
        mountOpts
    );

    cy.contains('document_alpha.pdf').should('be.visible');
    cy.contains('document_beta.docx').should('be.visible');
    cy.contains('Processing').should('be.visible');
    cy.contains('Ready for Review').should('be.visible');
  });

  it('shows empty state when no documents', () => {
    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
        mountOpts
    );
    cy.contains('No documents have been added for this case.').should('be.visible');
  });

  it('disables the upload button if the case is finalised', () => {
    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={true} />,
        mountOpts
    );

    cy.contains('button', 'Add Document').should('be.disabled');
    cy.contains('button', 'Add Document').trigger('mouseover', { force: true });
    cy.contains('This case is finalised and no longer accepts new documents.').should('be.visible');
  });
  it('opens upload dialog and lists selected files', () => {
    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
        mountOpts
    );

    cy.contains('button', 'Add Document').click();
    cy.contains('Add Document').should('be.visible');

    cy.get('#file-upload-input').selectFile({
      contents: Cypress.Buffer.from('file content'),
      fileName: 'test.pdf',
      mimeType: 'application/pdf'
    }, { force: true });

    cy.contains('Files to upload:').should('be.visible');
    cy.contains('test.pdf').should('be.visible');
  });

  it('allows removing a file from the upload list', () => {
    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
        mountOpts
    );

    cy.contains('button', 'Add Document').click();
    cy.get('#file-upload-input').selectFile({ contents: Cypress.Buffer.from('a'), fileName: 'file-to-remove.txt' }, { force: true });

    cy.contains('li', 'file-to-remove.txt').should('be.visible');
    cy.contains('li', 'file-to-remove.txt').find('button[aria-label="delete"]').click();
    cy.contains('li', 'file-to-remove.txt').should('not.exist');
    cy.contains('Files to upload:').should('not.exist');
  });

  context('Drag and Drop', () => {
    it('should add dropped files to the list', () => {
      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );

      cy.contains('button', 'Add Document').click();

      const dropzone = cy.get('[role="dialog"]').contains('Drag & drop files here').parent().parent();

      cy.window().then((win) => {
        const file = new win.File(['content'], 'dropped-file.pdf', { type: 'application/pdf' });
        
        const fileList = {
          0: file,
          length: 1,
          item: (index) => fileList[index]
        };

        dropzone.trigger('drop', { dataTransfer: { files: fileList, types: ['Files'] } });
      });

      cy.contains('Files to upload:').should('be.visible');
      cy.contains('li', 'dropped-file.pdf').should('be.visible');
    });
  });

  context('User Interactions with API calls', () => {
    beforeEach(() => {
      cy.intercept('GET', `/api/cases/documents/*`).as('getDocumentRequest');
    });

    it('uploads files successfully and calls onUpdate', () => {
      cy.intercept('POST', `/api/cases/${caseId}/documents`, {
        statusCode: 201, body: [
          {
            "id": "fea19d1a-61b5-4850-a75d-6cbb6081a90a",
            "original_file": "original_file.pdf",
            "filename": "new-cool-name",
            "file_type": ".docx",
            "status": "Processing",
            "extracted_text": null,
            "uploaded_at": "2025-12-03T21:33:55.651034Z",
            "redactions": []
          }
        ]
      }).as('uploadRequest');
      const onUpdate = cy.stub().as('onUpdate');
      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={onUpdate} isCaseFinalised={false} />,
          mountOpts
      );
      cy.contains('button', 'Add Document').click();
      cy.get('#file-upload-input').selectFile({ contents: Cypress.Buffer.from('a'), fileName: 'upload.pdf' }, { force: true });
      cy.get('.MuiDialogActions-root').contains('button', 'Upload').click();

      cy.wait('@uploadRequest');
      cy.get('@onUpdate').should('have.been.calledOnce');
      cy.contains('Documents uploaded successfully.').should('be.visible');
    });

    it('shows upload error toast when service rejects with detail', () => {
      cy.intercept('POST', `/api/cases/${caseId}/documents`, { statusCode: 500, body: { detail: 'Server is on fire' } }).as('uploadRequest');

      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );
      cy.contains('button', 'Add Document').click({ force: true });
      cy.get('#file-upload-input').selectFile({ contents: Cypress.Buffer.from('a'), fileName: 'big.pdf' }, { force: true });
      cy.get('.MuiDialogActions-root').contains('button', 'Upload').click();

      cy.wait('@uploadRequest');
      cy.contains('Server is on fire').should('be.visible');
    });

    it('shows confirmation dialog when delete is clicked', () => {
      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );
      cy.contains('li', 'document_beta.docx').find('button[aria-label="delete"]').click();

      cy.contains('Delete Document').should('be.visible');
      cy.contains('"document_beta.docx"').should('be.visible');
      cy.contains('button', 'Delete').should('be.visible');
      cy.contains('button', 'Cancel').should('be.visible');
    });

    it('does not delete when confirmation is cancelled', () => {
      cy.intercept('DELETE', '/api/cases/documents/*').as('deleteRequest');

      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );
      cy.contains('li', 'document_beta.docx').find('button[aria-label="delete"]').click();
      cy.contains('button', 'Cancel').click();

      cy.contains('Delete Document').should('not.exist');
      cy.get('@deleteRequest.all').should('have.length', 0);
    });

    it('deletes a document successfully and calls onUpdate', () => {
      cy.intercept('DELETE', '/api/cases/documents/*', { statusCode: 204 }).as('deleteRequest');
      const onUpdate = cy.stub().as('onUpdate');
      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={docs} onUpdate={onUpdate} isCaseFinalised={false} />,
          mountOpts
      );
      cy.get('li').first().find('button[aria-label="delete"]').click();
      cy.get('[role="dialog"]').contains('button', 'Delete').click();

      cy.wait('@deleteRequest');
      cy.get('@onUpdate').should('have.been.calledOnce');
      cy.contains('Document deleted.').should('be.visible');
    });

    it('shows a spinner and disables buttons while deletion is in progress', () => {
      cy.intercept('DELETE', '/api/cases/documents/*', (req) => {
        req.reply({ statusCode: 204, delay: 500 });
      }).as('deleteRequest');

      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );
      cy.get('li').first().find('button[aria-label="delete"]').click();
      cy.get('[role="dialog"]').contains('button', 'Delete').click();

      cy.get('[role="dialog"]').contains('button', 'Delete').should('be.disabled');
      cy.get('[role="dialog"]').contains('button', 'Cancel').should('be.disabled');
      cy.get('[role="dialog"]').find('[role="progressbar"]').should('exist');

      cy.wait('@deleteRequest');
    });

    it('shows delete error toast when service rejects', () => {
      cy.intercept('DELETE', '/api/cases/documents/*', { statusCode: 500 }).as('deleteRequest');

      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );
      cy.get('li').last().find('button[aria-label="delete"]').click();
      cy.get('[role="dialog"]').contains('button', 'Delete').click();

      cy.wait('@deleteRequest');
      cy.contains('Failed to delete document. Please try again.').should('be.visible');
    });

    it('allows renaming a file before upload', () => {
      cy.intercept('POST', `/api/cases/${caseId}/documents`, {
        statusCode: 201, body: [
          {
            "id": "fea19d1a-61b5-4850-a75d-6cbb6081a90a",
            "original_file": "original_file.pdf",
            "filename": "new-cool-name",
            "file_type": ".docx",
            "status": "Processing",
            "extracted_text": null,
            "uploaded_at": "2025-12-03T21:33:55.651034Z",
            "redactions": []
          }
        ]
      }).as('uploadRequest');
      const onUpdate = cy.stub().as('onUpdate');
      cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={onUpdate} isCaseFinalised={false} />,
        mountOpts
      );

      cy.contains('button', 'Add Document').click();

      cy.get('#file-upload-input').selectFile({
        contents: Cypress.Buffer.from('file content'),
        fileName: 'original-name.pdf',
        mimeType: 'application/pdf'
      }, { force: true });
      
      cy.contains('li', 'original-name.pdf').within(() => {
        cy.get('input[value="original-name"]').clear().type('new-cool-name');
      });

      cy.get('.MuiDialogActions-root').contains('button', 'Upload').click();
      
      cy.wait('@uploadRequest').then((interception) => {
        cy.get('@onUpdate').should('have.been.calledOnce');
        const body = interception.request.body;
        if (typeof body === 'string') {
          expect(body).to.include('filename="new-cool-name.pdf"');
          expect(body).to.include('name="original_file"');
        } else if (body && typeof body === 'object') {
          const files = body['original_file'];
          const file = Array.isArray(files) ? files[0] : files;
          if (file && file.name) {
            expect(file.name).to.equal('new-cool-name.pdf');
          }
        }
      });
    });

    context('Paste Text tab', () => {
      it('shows paste tab with name field and textarea', () => {
        cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
        );
        cy.contains('button', 'Add Document').click();
        cy.contains('[role="tab"]', 'Paste Text').click();
        cy.get('[role="dialog"]').find('input').filter(':visible').should('exist');
        cy.get('[role="dialog"]').find('textarea').filter(':visible').should('exist');
      });

      it('keeps Create button disabled until both fields are filled', () => {
        cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
        );
        cy.contains('button', 'Add Document').click();
        cy.contains('[role="tab"]', 'Paste Text').click();
        cy.get('[role="dialog"]').contains('button', 'Create').should('be.disabled');
        cy.get('[role="dialog"]').find('input').filter(':visible').first().type('My Report');
        cy.get('[role="dialog"]').contains('button', 'Create').should('be.disabled');
      });

      it('submits pasted text as a .txt file and calls onUpdate', () => {
        cy.intercept('POST', `/api/cases/${caseId}/documents`, {
          statusCode: 201, body: [{
            id: 'txt-doc-1',
            filename: 'My Report.txt',
            file_type: '.txt',
            status: 'Processing',
            extracted_text: null,
            uploaded_at: '2026-06-27T10:00:00Z',
            redactions: []
          }]
        }).as('createRequest');
        const onUpdate = cy.stub().as('onUpdate');
        cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={onUpdate} isCaseFinalised={false} />,
          mountOpts
        );
        cy.contains('button', 'Add Document').click();
        cy.contains('[role="tab"]', 'Paste Text').click();
        cy.get('[role="dialog"]').find('input').filter(':visible').type('My Report');
        cy.get('[role="dialog"]').find('textarea').first().type('Some document content here.');
        cy.get('[role="dialog"]').contains('button', 'Create').click();

        cy.wait('@createRequest');
        cy.get('@onUpdate').should('have.been.calledOnce');
        cy.contains('Document created successfully.').should('be.visible');
      });

      it('shows error toast when paste submission fails', () => {
        cy.intercept('POST', `/api/cases/${caseId}/documents`, { statusCode: 500 }).as('createRequest');
        cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
        );
        cy.contains('button', 'Add Document').click();
        cy.contains('[role="tab"]', 'Paste Text').click();
        cy.get('[role="dialog"]').find('input').filter(':visible').type('Bad Doc');
        cy.get('[role="dialog"]').find('textarea').first().type('Some text.');
        cy.get('[role="dialog"]').contains('button', 'Create').click();

        cy.wait('@createRequest');
        cy.contains('Failed to upload document(s). Please try again.').should('be.visible');
      });

      it('resets paste fields when dialog is closed and reopened', () => {
        cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
        );
        cy.contains('button', 'Add Document').click();
        cy.contains('[role="tab"]', 'Paste Text').click();
        cy.get('[role="dialog"]').find('input').filter(':visible').type('Draft');
        cy.get('[role="dialog"]').find('textarea').first().type('Draft content.');
        cy.get('[role="dialog"]').contains('button', 'Cancel').click();

        cy.contains('button', 'Add Document').click();
        cy.contains('[role="tab"]', 'Paste Text').click();
        cy.get('[role="dialog"]').find('input').filter(':visible').should('have.value', '');
        cy.get('[role="dialog"]').find('textarea').first().should('have.value', '');
      });
    });

    context('Re-submit document for processing', () => {
      it('resubmits a document successfully and calls onUpdate', () => {
        cy.intercept('POST', '/api/cases/documents/*/resubmit', { statusCode: 200 }).as('resubmitRequest');
        const onUpdate = cy.stub().as('onUpdate');
        cy.fullMount(
            <CaseDocuments caseId={caseId} documents={docs} onUpdate={onUpdate} isCaseFinalised={false} />,
            mountOpts
        );
        cy.contains('li', 'document_gamma.pdf').within(() => {
          cy.get('button[aria-label="resubmit"]').click();
        });

        cy.wait('@resubmitRequest');
        cy.get('@onUpdate').should('have.been.calledOnce');
        cy.contains('Document resubmitted for processing.').should('be.visible');
      });

      it('shows resubmit error toast when service rejects', () => {
        cy.intercept('POST', '/api/cases/documents/*/resubmit', { statusCode: 500 }).as('resubmitRequest');
        
        cy.fullMount(
            <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={false} />,
            mountOpts
        );
        cy.contains('li', 'document_gamma.pdf').within(() => {
          cy.get('button[aria-label="resubmit"]').click();
        });

        cy.wait('@resubmitRequest');
        cy.contains('Failed to resubmit document. Please try again.').should('be.visible');
      });
    });
  });
});