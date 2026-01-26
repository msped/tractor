import React from 'react';
import { TrainingDocList } from '@/components/TrainingDocList';

describe('<TrainingDocList />', () => {
    const mockDocs = [
        {
            id: 'doc-1',
            name: 'document_alpha.pdf',
            created_by_username: 'user_one',
            created_at: '2024-05-20T10:00:00Z',
            processed: true,
        },
        {
            id: 'doc-2',
            name: 'document_beta.docx',
            created_by_username: 'user_two',
            created_at: '2024-05-21T12:30:00Z',
            processed: false,
        },
    ];

    const mountOptions = {
        mockSession: {
            access_token: 'fake-token',
            status: 'authenticated',
        },
    };

    it('renders the list of documents correctly', () => {
        cy.fullMount(<TrainingDocList docs={mockDocs} />, mountOptions);

        cy.contains('h6', 'Uploaded Training Documents').should('be.visible');

        cy.contains('tr', 'document_alpha.pdf').within(() => {
            cy.contains('td', 'user_one').should('be.visible');
            cy.contains('td', new Date(mockDocs[0].created_at).toLocaleString()).should('be.visible');
            cy.contains('span', 'Processed').parent().should('be.visible').and('have.css', 'background-color', 'rgb(46, 125, 50)');
        });

        cy.contains('tr', 'document_beta.docx').within(() => {
            cy.contains('td', 'user_two').should('be.visible');
            cy.contains('span', 'Unprocessed').parent().should('be.visible').and('have.css', 'background-color', 'rgb(237, 108, 2)');
        });
    });

    it('shows an empty table when no documents are provided', () => {
        cy.fullMount(<TrainingDocList docs={[]} />, mountOptions);
        cy.get('tbody tr').should('not.exist');
    });

    context('Delete Document Flow', () => {
        it('opens confirmation dialog on delete click, then cancels', () => {
            const deleteStub = cy.stub().as('deleteTrainingDoc');

            cy.fullMount(<TrainingDocList docs={mockDocs} deleteTrainingDoc={deleteStub} />, mountOptions);

            cy.contains('tr', 'document_alpha.pdf').find('button[aria-label="Delete Document"]').click();

            cy.get('[role="dialog"]').should('be.visible');
            cy.contains('Confirm Deletion').should('be.visible');
            cy.contains('Are you sure you want to delete "document_alpha.pdf"?').should('be.visible');

            cy.get('[role="dialog"]').contains('button', 'Cancel').click();
            cy.get('[role="dialog"]').should('not.exist');

            expect(deleteStub).not.to.be.called;
        });

        it('successfully deletes a document after confirmation', () => {
            const deleteStub = cy.stub().as('deleteTrainingDoc').resolves();
            const refreshDocsStub = cy.stub().as('refreshDocs');
            cy.fullMount(
                <TrainingDocList docs={mockDocs} deleteTrainingDoc={deleteStub} refreshDocs={refreshDocsStub} />,
                mountOptions
            );

            cy.contains('tr', 'document_alpha.pdf').find('button[aria-label="Delete Document"]').click();
            cy.get('[role="dialog"]').contains('button', 'Delete').click();
            cy.contains('Document deleted successfully.').should('be.visible');
            cy.get('@deleteTrainingDoc').should('have.been.calledOnceWith', 'doc-1');
            cy.get('@refreshDocs').should('have.been.calledOnce');
            cy.get('[role="dialog"]').should('not.exist');
        });

        it('shows an error toast if deletion fails', () => {
            const errorMessage = 'Permission denied.';
            const deleteStub = cy.stub().as('deleteTrainingDoc').rejects(new Error(errorMessage));

            cy.fullMount(<TrainingDocList docs={mockDocs} deleteTrainingDoc={deleteStub} />, mountOptions);

            cy.contains('tr', 'document_beta.docx').find('button[aria-label="Delete Document"]').click();
            cy.get('[role="dialog"]').contains('button', 'Delete').click();
            cy.contains(errorMessage).should('be.visible');
            cy.get('@deleteTrainingDoc').should('have.been.calledOnceWith', 'doc-2');
            cy.get('[role="dialog"]').should('not.exist');
        });
    });
});