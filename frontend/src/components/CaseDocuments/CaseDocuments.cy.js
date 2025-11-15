import React from 'react';
import { CaseDocuments } from './CaseDocuments';
import apiClient from '@/api/apiClient';

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

  it('opens upload dialog and lists selected files', () => {
    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
        mountOpts
    );

    cy.contains('button', 'Upload Document').click();
    cy.contains('Upload New Document').should('be.visible');

    cy.window().then((win) => {
      const file = new win.File(['hello'], 'test.pdf', { type: 'application/pdf' });
      const data = new win.DataTransfer();
      data.items.add(file);
      cy.get('#file-upload-input').then($input => {
        $input[0].files = data.files;
        cy.wrap($input).trigger('change', { force: true });
      });
    });

    cy.contains('Files to upload:').should('be.visible');
    cy.contains('test.pdf').should('be.visible');
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

  it('allows renaming a file before upload', () => {
    const onUpdate = cy.stub().as('onUpdate');
    const postStub = cy.stub(apiClient, 'post').resolves({
        body: {
            id: 'doc-123',
            filename: 'new-cool-name.pdf',
            file_type: 'pdf',
            uploaded_at: new Date().toISOString(),
            status: 'Processing'
        }
    }).as('postApi');

    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={onUpdate} isCaseFinalised={false} />,
        mountOpts
    );

    cy.contains('button', 'Upload Document').click();

    cy.window().then((win) => {
      const file = new win.File(['content'], 'original-name.pdf', { type: 'application/pdf' });
      const dt = new win.DataTransfer();
      dt.items.add(file);
      cy.get('#file-upload-input').then($input => {
        $input[0].files = dt.files;
        cy.wrap($input).trigger('change', { force: true });
      });
    });
    
    cy.contains('li', 'original-name.pdf').within(() => {
        cy.get('input[value="original-name"]').clear().type('new-cool-name');
    });

    cy.get('[role="dialog"]').contains('button', 'Upload').click();

    cy.get('@postApi').its('firstCall.args.1').invoke('get', 'original_file').its('name').should('eq', 'new-cool-name.pdf');
  });

  it('uploads files successfully and calls onUpdate', () => {
    const onUpdate = cy.stub().as('onUpdate');
    const postStub = cy.stub(apiClient, 'post').resolves({}).as('postApi');

    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={onUpdate} isCaseFinalised={false} />,
        mountOpts
    );

    cy.contains('button', 'Upload Document').click();

    cy.window().then((win) => {
      const file = new win.File(['content'], 'upload.pdf', { type: 'application/pdf' });
      const dt = new win.DataTransfer();
      dt.items.add(file);
      cy.get('#file-upload-input').then($input => {
        $input[0].files = dt.files;
        cy.wrap($input).trigger('change', { force: true });
      });
      cy.get('[role="dialog"]').contains('button', 'Upload').click();
    });


    cy.get('@postApi').should('have.been.calledOnce');
    cy.get('@onUpdate').should('have.been.calledOnce');
    cy.contains('Documents uploaded successfully.').should('be.visible');
  });

  it('shows upload error toast when apiClient.post rejects with detail', () => {
    const err = { response: { data: { detail: 'File too large' } } };
    cy.stub(apiClient, 'post').rejects(err).as('postErr');

    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={[]} onUpdate={() => {}} isCaseFinalised={false} />,
        mountOpts
    );

    cy.contains('button', 'Upload Document').click();

    cy.window().then((win) => {
      const file = new win.File(['x'], 'big.pdf', { type: 'application/pdf' });
      const dt = new win.DataTransfer();
      dt.items.add(file);
      cy.get('#file-upload-input').then($input => {
        $input[0].files = dt.files;
        cy.wrap($input).trigger('change', { force: true });
      });
    });

    cy.get('[role="dialog"]').contains('button', 'Upload').click();
    cy.contains('Upload failed: File too large').should('be.visible');
  });

  it('deletes a document successfully and calls onUpdate', () => {
    const onUpdate = cy.stub().as('onUpdate');
    cy.stub(apiClient, 'delete').resolves({}).as('deleteApi');

    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={docs} onUpdate={onUpdate} isCaseFinalised={false} />,
        mountOpts
    );
    cy.get('li').first().find('button[aria-label="delete"]').click();

    cy.get('@deleteApi').should('have.been.calledOnce');
    cy.get('@onUpdate').should('have.been.calledOnce');
    cy.contains('Document deleted.').should('be.visible');
  });

  it('shows delete error toast when apiClient.delete rejects', () => {
    cy.stub(apiClient, 'delete').rejects(new Error('nope')).as('deleteErr');

    cy.fullMount(
        <CaseDocuments caseId={caseId} documents={docs} onUpdate={() => {}} isCaseFinalised={false} />,
        mountOpts
    );

    cy.get('li').last().find('button[aria-label="delete"]').click();

    cy.contains('Failed to delete document. Please try again.').should('be.visible');
  });
});