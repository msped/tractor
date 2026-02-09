import React from 'react';
import { DocumentViewComponent } from './DocumentViewComponent';

describe('<DocumentViewComponent />', () => {
    const mockCaseId = 'case-123';
    const mockDocument = {
        id: 'doc-456',
        filename: 'test-document.pdf',
        extracted_text: 'This is some sample text with sensitive information and also some op data.',
    };
    const mockRedactions = [ 
        { start_char: 30, end_char: 51, text: 'sensitive information', redaction_type: 'PII' },
        { start_char: 66, end_char: 73, text: 'op data', redaction_type: 'OP_DATA' }
    ];

    beforeEach(() => {
        cy.fullMount(
            <DocumentViewComponent
                caseId={mockCaseId}
                document={mockDocument}
                redactions={mockRedactions}
            />
        );
    });

    it('renders the main components correctly', () => {
        cy.contains('a', 'Back to Case')
            .should('be.visible')
            .and('have.attr', 'href', `/cases/${mockCaseId}`);

        cy.contains('h1', mockDocument.filename).should('be.visible');

        cy.contains('label', 'Show Color-coded Redactions').should('be.visible');
        cy.get('input[type="checkbox"]').should('not.be.checked');
    });

    it('renders text with redactions in "final" view by default', () => {
        cy.contains('This is some sample text with ').should('be.visible');

        cy.contains('span', 'sensitive information')
            .should('be.visible')
            .and('have.css', 'background-color', 'rgb(0, 0, 0)')
            .and('have.css', 'color', 'rgb(0, 0, 0)');

        cy.contains('span', 'op data')
            .should('be.visible')
            .and('have.css', 'background-color', 'rgb(0, 0, 0)')
            .and('have.css', 'color', 'rgb(0, 0, 0)');
    });

    it('renders font size increase and decrease buttons', () => {
        cy.get('button[aria-label="Decrease font size"]').should('be.visible');
        cy.get('button[aria-label="Increase font size"]').should('be.visible');
    });

    it('increases font size when A+ is clicked', () => {
        cy.get('.MuiPaper-root').should('have.css', 'font-size', '16px');

        cy.get('button[aria-label="Increase font size"]').click();

        cy.get('.MuiPaper-root').should('have.css', 'font-size').and('not.eq', '16px');
    });

    it('decreases font size when A- is clicked', () => {
        cy.get('.MuiPaper-root').should('have.css', 'font-size', '16px');

        cy.get('button[aria-label="Decrease font size"]').click();

        cy.get('.MuiPaper-root').should('have.css', 'font-size').and('not.eq', '16px');
    });

    it('disables decrease button at minimum font size', () => {
        cy.get('button[aria-label="Decrease font size"]').click();
        cy.get('button[aria-label="Decrease font size"]').click();

        cy.get('button[aria-label="Decrease font size"]').should('be.disabled');
    });

    it('disables increase button at maximum font size', () => {
        cy.get('button[aria-label="Increase font size"]').click();
        cy.get('button[aria-label="Increase font size"]').click();
        cy.get('button[aria-label="Increase font size"]').click();

        cy.get('button[aria-label="Increase font size"]').should('be.disabled');
    });

    it('toggles to color-coded view and back', () => {
        cy.contains('span', 'sensitive information').should('have.css', 'background-color', 'rgb(0, 0, 0)');
        cy.contains('span', 'op data').should('have.css', 'background-color', 'rgb(0, 0, 0)');


        cy.get('input[type="checkbox"]').check({ force: true });
        cy.get('input[type="checkbox"]').should('be.checked');

        cy.contains('span', 'sensitive information').should('have.css', 'background-color', 'rgba(46, 204, 113, 0.7)');
        cy.contains('span', 'op data').should('have.css', 'background-color', 'rgba(0, 221, 255, 0.7)');

        cy.get('input[type="checkbox"]').uncheck({ force: true });
        cy.get('input[type="checkbox"]').should('not.be.checked');

        cy.contains('span', 'sensitive information').should('have.css', 'background-color', 'rgb(0, 0, 0)');
        cy.contains('span', 'op data').should('have.css', 'background-color', 'rgb(0, 0, 0)');
    });
});