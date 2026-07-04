import React from 'react';
import { DownloadTrainingDocButton } from './DownloadTrainingDocButton';

describe('<DownloadTrainingDocButton />', () => {
    const defaultProps = {
        fileUrl: '/media/training_docs/test-document.docx',
        filename: 'test-document.docx',
    };

    it('renders the download button', () => {
        cy.fullMount(<DownloadTrainingDocButton {...defaultProps} />);

        cy.get('button').should('be.visible');
        cy.get('[data-testid="DownloadIcon"]').should('be.visible');
    });

    it('fetches the file through the API client on click', () => {
        cy.intercept('GET', '**/media/training_docs/test-document.docx', {
            statusCode: 200,
            body: 'file-bytes',
        }).as('downloadFile');

        cy.fullMount(<DownloadTrainingDocButton {...defaultProps} />);

        cy.get('button').click();
        cy.wait('@downloadFile');
    });

    it('shows an error toast when the download fails', () => {
        cy.intercept('GET', '**/media/training_docs/test-document.docx', {
            statusCode: 401,
        }).as('downloadFile');

        cy.fullMount(<DownloadTrainingDocButton {...defaultProps} />);

        cy.get('button').click();
        cy.wait('@downloadFile');
        cy.contains('Failed to download the document.').should('be.visible');
    });

    it('shows tooltip on hover', () => {
        cy.fullMount(<DownloadTrainingDocButton {...defaultProps} />);

        cy.get('button').trigger('mouseover');
        cy.contains('Download').should('be.visible');
    });
});
