import React from 'react';
import { DownloadTrainingDocButton } from './DownloadTrainingDocButton';

describe('<DownloadTrainingDocButton />', () => {
    const defaultProps = {
        fileUrl: '/media/training_docs/test-document.docx',
        filename: 'test-document.docx',
    };

    it('renders the download button', () => {
        cy.fullMount(<DownloadTrainingDocButton {...defaultProps} />);

        cy.get('a[download]').should('be.visible');
        cy.get('[data-testid="DownloadIcon"]').should('be.visible');
    });

    it('has the correct href attribute', () => {
        cy.fullMount(<DownloadTrainingDocButton {...defaultProps} />);

        cy.get('a[download]')
            .should('have.attr', 'href', defaultProps.fileUrl);
    });

    it('has the correct download attribute with filename', () => {
        cy.fullMount(<DownloadTrainingDocButton {...defaultProps} />);

        cy.get('a[download]')
            .should('have.attr', 'download', defaultProps.filename);
    });

    it('shows tooltip on hover', () => {
        cy.fullMount(<DownloadTrainingDocButton {...defaultProps} />);

        cy.get('a[download]').trigger('mouseover');
        cy.contains('Download').should('be.visible');
    });
});
