import React from 'react';
import { DocumentListItem } from './DocumentListItem';
import * as documentService from '@/services/documentService';

describe('<DocumentListItem />', () => {
    const caseId = 'case-123';
    const baseDoc = {
        id: 'doc-456',
        filename: 'test-document.pdf',
        uploaded_at: '2024-01-15T10:30:00Z',
        status: 'Ready for Review',
    };

    const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

    it('renders document details correctly', () => {
        cy.fullMount(
            <DocumentListItem doc={baseDoc} caseId={caseId} onDelete={() => {}} handleDocumentUpdate={() => {}} isCaseFinalised={false} />,
            mountOpts
        );

        cy.contains('test-document.pdf').should('be.visible');
        cy.contains('Uploaded: 15/01/2024').should('be.visible');
        cy.contains('Ready for Review').should('be.visible');
    });

    context('Status-based rendering', () => {
        it('shows a "Review" button for "Ready for Review" status', () => {
            cy.fullMount(
                <DocumentListItem doc={baseDoc} caseId={caseId} onDelete={() => {}} handleDocumentUpdate={() => {}} isCaseFinalised={false} />,
                mountOpts
            );

            cy.contains('a', 'Review')
                .should('be.visible')
                .and('have.attr', 'href', `/cases/${caseId}/document/${baseDoc.id}/review`);
            cy.contains('a', 'Open').should('not.exist');
        });

        it('shows an "Open" button for "Completed" status', () => {
            const completedDoc = { ...baseDoc, status: 'Completed' };
            cy.fullMount(
                <DocumentListItem doc={completedDoc} caseId={caseId} onDelete={() => {}} handleDocumentUpdate={() => {}} isCaseFinalised={false} />,
                mountOpts
            );

            cy.contains('a', 'Open')
                .should('be.visible')
                .and('have.attr', 'href', `/cases/${caseId}/document/${baseDoc.id}/view`);
            cy.contains('a', 'Review').should('not.exist');
        });

        it('shows a spinner icon for "Processing" status', () => {
            const processingDoc = { ...baseDoc, status: 'Processing' };
            cy.fullMount(
                <DocumentListItem doc={processingDoc} caseId={caseId} onDelete={() => {}} handleDocumentUpdate={() => {}} isCaseFinalised={false} />,
                mountOpts
            );

            cy.get('[role="progressbar"]').should('be.visible').parent().contains('Processing');
            cy.contains('button', 'Review').should('not.exist');
            cy.contains('button', 'Open').should('not.exist');
        });
    });

    context('Delete functionality', () => {
        it('calls the onDelete prop when the delete button is clicked', () => {
            const onDelete = cy.stub().as('onDeleteStub');
            cy.fullMount(
                <DocumentListItem doc={baseDoc} caseId={caseId} onDelete={onDelete} handleDocumentUpdate={() => {}} isCaseFinalised={false} />,
                mountOpts
            );

            cy.get('button[aria-label="delete"]').click();
            cy.get('@onDeleteStub').should('have.been.calledOnceWith', baseDoc.id);
        });

        it('disables the delete button when the case is finalised', () => {
            cy.fullMount(
                <DocumentListItem doc={baseDoc} caseId={caseId} onDelete={() => {}} handleDocumentUpdate={() => {}} isCaseFinalised={true} />,
                mountOpts
            );

            cy.get('button[aria-label="delete"]').should('be.disabled');
        });

        it('shows a tooltip on the disabled delete button when case is finalised', () => {
            cy.fullMount(
                <DocumentListItem doc={baseDoc} caseId={caseId} onDelete={() => {}} handleDocumentUpdate={() => {}} isCaseFinalised={true} />,
                mountOpts
            );

            cy.get('button[aria-label="delete"]').trigger('mouseover', { force: true });
            cy.contains('Cannot delete documents from a finalised case.').should('be.visible');
        });
    });

    context('Polling for status updates', () => {
        beforeEach(() => {
            cy.clock();
        });

        it('polls for status and calls update when status changes from "Processing"', () => {
            const processingDoc = { ...baseDoc, status: 'Processing' };
            const updatedDoc = { ...baseDoc, status: 'Ready for Review' };
            const handleUpdate = cy.stub().as('handleUpdateStub');

            cy.intercept('GET', `/api/cases/documents/${processingDoc.id}`, {status: 200, body: updatedDoc }).as('getDocumentStub');

            cy.fullMount(
                <DocumentListItem
                    doc={processingDoc}
                    caseId={caseId}
                    onDelete={() => {}}
                    handleDocumentUpdate={handleUpdate}
                    isCaseFinalised={false}
                />,
                mountOpts
            );

            cy.contains('Processing').should('be.visible');

            cy.tick(5000);

            cy.get('@handleUpdateStub').should('have.been.calledOnce');
        });

        it('does not poll if status is not "Processing"', () => {
            const handleUpdate = cy.stub().as('handleUpdateStub');
            cy.stub(documentService, 'getDocument').as('getDocumentStub');

            cy.fullMount(
                <DocumentListItem doc={baseDoc} caseId={caseId} onDelete={() => {}} handleDocumentUpdate={handleUpdate} isCaseFinalised={false} />,
                mountOpts
            );

            cy.tick(10000);
            cy.get('@getDocumentStub').should('not.have.been.called');
        });
    });

    context('Resubmission handling', () => {
        it('shows "Resubmit" button for "Error" status and calls onResubmit when clicked', () => {
            const resubmitDoc = { ...baseDoc, status: 'Error' };
            const onResubmit = cy.stub().as('onResubmitStub');

            cy.fullMount(
                <DocumentListItem doc={resubmitDoc} caseId={caseId} onDelete={() => {}} onResubmit={onResubmit} handleDocumentUpdate={() => {}} isCaseFinalised={false} />,
                mountOpts
            );

            cy.get('button[aria-label="resubmit"]')
                .should('be.visible')
                .click();

            cy.get('@onResubmitStub').should('have.been.calledOnceWith', resubmitDoc.id);
        });

        it('disables the resubmit button when the case is finalised', () => {
            const resubmitDoc = { ...baseDoc, status: 'Error' };
            cy.fullMount(
                <DocumentListItem doc={resubmitDoc} caseId={caseId} onDelete={() => {}} onResubmit={() => {}} handleDocumentUpdate={() => {}} isCaseFinalised={true} />,
                mountOpts
            );

            cy.get('button[aria-label="resubmit"]').should('be.disabled');
        });
    });
});