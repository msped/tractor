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

        // Stub the programmatic anchor click so the browser doesn't write
        // the file into cypress/downloads.
        cy.window().then((win) => {
            cy.stub(win.HTMLAnchorElement.prototype, 'click').as('anchorClick');
        });

        cy.get('button').click();
        cy.wait('@downloadFile');
        cy.get('@anchorClick').should('have.been.calledOnce');
    });

    it('downloads absolute URLs natively without the API client', () => {
        // Presigned cloud-storage URLs carry their own auth; they must not
        // be fetched through apiClient (which would attach the JWT).
        cy.intercept('GET', '**/package.docx').as('apiFetch');

        cy.fullMount(
            <DownloadTrainingDocButton
                fileUrl="https://storage.example.com/media/package.docx?sig=abc"
                filename="package.docx"
            />
        );

        cy.window().then((win) => {
            cy.stub(win.HTMLAnchorElement.prototype, 'click').as('anchorClick');
        });

        cy.get('button').click();
        cy.get('@anchorClick').should('have.been.calledOnce');
        cy.get('@apiFetch.all').should('have.length', 0);
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
