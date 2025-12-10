import React from 'react';
import { TrainingUpload } from './TrainingUpload';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

describe('<TrainingUpload />', () => {
  beforeEach(() => {
    cy.intercept('POST', '/api/training-docs', { statusCode: 201 }).as('uploadTrainingDoc');
    cy.intercept('POST', '/api/training/run-now', { statusCode: 200, body: { documents: 5 }}).as('runManualTraining');
  });

  it('renders correctly and shows initial state', () => {
    cy.fullMount(<TrainingUpload unprocessedDocsCount={0} />, mountOpts);
    cy.contains('Upload Training Document (.docx)').should('be.visible');
    cy.contains('Drag & drop .docx files here').should('be.visible');
    cy.contains('button', 'Run Training on 0 Unprocessed Document(s)').should('be.disabled');
  });

  it('enables the "Run Training" button when there are unprocessed docs', () => {
    cy.fullMount(<TrainingUpload unprocessedDocsCount={5} />, mountOpts);
    cy.contains('button', 'Run Training on 5 Unprocessed Document(s)').should('be.enabled');
  });

  context('File Upload', () => {
    it('uploads a .docx file successfully via click', () => {
      cy.fullMount(<TrainingUpload unprocessedDocsCount={0} />, mountOpts);

      // Use .selectFile on the hidden input to simulate a user clicking and choosing a file
      cy.get('input[type="file"]').selectFile({
        contents: Cypress.Buffer.from('file content'),
        fileName: 'test.docx',
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      }, { force: true });

      cy.wait('@uploadTrainingDoc');
      cy.contains('1 document(s) uploaded successfully.').should('be.visible');
    });

    it('uploads multiple .docx files successfully via drag and drop', () => {
      cy.fullMount(<TrainingUpload unprocessedDocsCount={0} />, mountOpts);
      
      // Use the file input directly for a more reliable multi-file test
      cy.get('input[type="file"]').selectFile([
        { contents: Cypress.Buffer.from('file1'), fileName: 'doc1.docx' },
        { contents: Cypress.Buffer.from('file2'), fileName: 'doc2.docx' }
      ], { force: true });

      // Wait for both requests to complete since we are uploading 2 files
      cy.wait(['@uploadTrainingDoc', '@uploadTrainingDoc']);
      cy.contains('2 document(s) uploaded successfully.').should('be.visible');
    });

    it('ignores non-docx files and shows a toast message', () => {
      cy.fullMount(<TrainingUpload unprocessedDocsCount={0} />, mountOpts);

      cy.get('input[type="file"]').selectFile([
        { contents: Cypress.Buffer.from('file1'), fileName: 'doc1.docx' },
        { contents: Cypress.Buffer.from('text file'), fileName: 'notes.txt' }
      ], { force: true });

      cy.wait('@uploadTrainingDoc')
      cy.contains('Some selected files were not .docx and have been ignored.').should('be.visible');
      cy.contains('1 document(s) uploaded successfully.').should('be.visible');
    });

    it('shows an error toast if the upload fails', () => {
      cy.intercept('POST', '/api/training-docs', { statusCode: 400, body: { detail: 'Network Failure' }})
        .as('uploadTrainingDoc');
      cy.fullMount(<TrainingUpload unprocessedDocsCount={0} />, mountOpts);

      cy.get('input[type="file"]').selectFile({ contents: Cypress.Buffer.from('a'), fileName: 'fail.docx' }, { force: true });

      cy.contains('An error occurred during upload: Network Failure').should('be.visible');
    });
  });

  context('Run Training', () => {
    it('calls the runManualTraining service and shows a success toast', () => {
      cy.fullMount(<TrainingUpload unprocessedDocsCount={5} />, mountOpts);

      cy.contains('button', 'Run Training on 5 Unprocessed Document(s)').click();

      cy.wait('@runManualTraining')
      cy.contains('Training started on 5 documents.').should('be.visible');
    });

    it('shows an error toast if running training fails', () => {
      cy.intercept('POST', '/api/training/run-now', { statusCode: 400, body: { detail: 'Training service offline' }})
        .as('runManualTraining');
      cy.fullMount(<TrainingUpload unprocessedDocsCount={5} />, mountOpts);

      cy.contains('button', 'Run Training on 5 Unprocessed Document(s)').click();

      cy.contains('Training service offline').should('be.visible');
    });
  });
});