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
  ];

  const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

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
    cy.contains('No documents have been uploaded for this case.').should('be.visible');
  });

  it('disables the upload button if the case is finalised', () => {
    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={true} />,
        mountOpts
    );

    cy.contains('button', 'Upload Document').should('be.disabled');
    cy.contains('button', 'Upload Document').trigger('mouseover', { force: true });
    cy.contains('This case is finalised and no longer accepts new documents.').should('be.visible');
  });
  it('opens upload dialog and lists selected files', () => {
    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
        mountOpts
    );

    cy.contains('button', 'Upload Document').click();
    cy.contains('Upload New Document').should('be.visible');

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

    cy.contains('button', 'Upload Document').click();
    cy.get('#file-upload-input').selectFile({ contents: Cypress.Buffer.from('a'), fileName: 'file-to-remove.txt' }, { force: true });

    cy.contains('li', 'file-to-remove.txt').should('be.visible');
    cy.contains('li', 'file-to-remove.txt').find('button[aria-label="delete"]').click();
    cy.contains('li', 'file-to-remove.txt').should('not.exist');
    cy.contains('Files to upload:').should('not.exist');
  });

  context('Drag and Drop', () => {
    it('should change border style on drag enter and leave', () => {
      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );

      cy.contains('button', 'Upload Document').click();

      const dropzone = cy.get('[role="dialog"]').contains('Drag & drop files here').parent().parent();

      dropzone.trigger('dragenter', { dataTransfer: {} });
      dropzone.should('have.css', 'border-color', 'rgba(0, 0, 0, 0.87)');
      dropzone.trigger('dragleave', { dataTransfer: {} });
      dropzone.should('have.css', 'border-color', 'rgba(0, 0, 0, 0.87)');
    });

    it('should add dropped files to the list', () => {
      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );

      cy.contains('button', 'Upload Document').click();

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
      cy.contains('button', 'Upload Document').click();
      cy.get('#file-upload-input').selectFile({ contents: Cypress.Buffer.from('a'), fileName: 'upload.pdf' }, { force: true });
      cy.get('[role="dialog"]').contains('button', 'Upload').click();

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
      cy.contains('button', 'Upload Document').click({ force: true });
      cy.get('#file-upload-input').selectFile({ contents: Cypress.Buffer.from('a'), fileName: 'big.pdf' }, { force: true });
      cy.get('[role="dialog"]').contains('button', 'Upload').click();

      cy.wait('@uploadRequest');
      cy.contains('Failed to upload document(s): Server is on fire').should('be.visible');
    });

    it('deletes a document successfully and calls onUpdate', () => {
      cy.intercept('DELETE', '/api/cases/documents/*', { statusCode: 204 }).as('deleteRequest');
      const onUpdate = cy.stub().as('onUpdate');
      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={docs} onUpdate={onUpdate} isCaseFinalised={false} />,
          mountOpts
      );
      cy.get('li').first().find('button[aria-label="delete"]').click();

      cy.wait('@deleteRequest');
      cy.get('@onUpdate').should('have.been.calledOnce');
      cy.contains('Document deleted.').should('be.visible');
    });

    it('shows delete error toast when service rejects', () => {
      cy.intercept('DELETE', '/api/cases/documents/*', { statusCode: 500 }).as('deleteRequest');
      
      cy.fullMount(
          <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={false} />,
          mountOpts
      );
      cy.get('li').last().find('button[aria-label="delete"]').click();

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

      cy.contains('button', 'Upload Document').click();

      cy.get('#file-upload-input').selectFile({
        contents: Cypress.Buffer.from('file content'),
        fileName: 'original-name.pdf',
        mimeType: 'application/pdf'
      }, { force: true });
      
      cy.contains('li', 'original-name.pdf').within(() => {
        cy.get('input[value="original-name"]').clear().type('new-cool-name');
      });

      cy.get('[role="dialog"]').contains('button', 'Upload').click();
      
      cy.wait('@uploadRequest').then((interception) => {
        cy.get('@onUpdate').should('have.been.calledOnce');
        cy.wrap(interception.request.body)
          .should('contain', 'filename="new-cool-name.pdf"')
          .and('contain', 'name="original_file"');
      });
    });
  });
});