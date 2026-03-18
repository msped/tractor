import React from 'react';
import { SWRConfig } from 'swr';
import { ExemptionTemplatesCard } from './ExemptionTemplatesCard';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

const mockTemplates = [
    { id: 1, name: 'S.40 - Personal Information', description: 'Personal data exemption' },
    { id: 2, name: 'S.42 - Legal Privilege', description: '' },
];

describe('<ExemptionTemplatesCard />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/cases/exemptions', { body: mockTemplates }).as('getTemplates');
    });

    it('renders the card title and description', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('Exemption Templates').should('be.visible');
        cy.contains('Configurable rejection reasons').should('be.visible');
    });

    it('displays templates returned from the API', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('S.40 - Personal Information').should('be.visible');
        cy.contains('Personal data exemption').should('be.visible');
        cy.contains('S.42 - Legal Privilege').should('be.visible');
        cy.contains('—').should('be.visible');
    });

    it('shows empty state when no templates exist', () => {
        cy.intercept('GET', '**/cases/exemptions', { body: [] }).as('getTemplatesEmpty');
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplatesEmpty');
        cy.contains('No exemption templates configured.').should('be.visible');
    });

    it('shows the add form when Add is clicked', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').should('be.visible');
        cy.get('input[aria-label="template description"]').should('be.visible');
        cy.get('button').contains('Save').should('be.disabled');
    });

    it('enables Save only when name is entered', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.get('button').contains('Add').click();
        cy.get('button').contains('Save').should('be.disabled');
        cy.get('input[aria-label="template name"]').type('S.43 - National Security');
        cy.get('button').contains('Save').should('be.enabled');
    });

    it('submits the new template and closes the form', () => {
        cy.intercept('POST', '**/cases/exemptions', {
            statusCode: 201,
            body: { id: 3, name: 'S.43 - National Security', description: '' },
        }).as('createTemplate');

        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').type('S.43 - National Security');
        cy.get('button').contains('Save').click();
        cy.wait('@createTemplate');
        cy.get('input[aria-label="template name"]').should('not.exist');
    });

    it('cancels the add form without submitting', () => {
        cy.intercept('POST', '**/cases/exemptions').as('createTemplate');

        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').type('Something');
        cy.get('button').contains('Cancel').click();
        cy.get('input[aria-label="template name"]').should('not.exist');
        cy.get('@createTemplate.all').should('have.length', 0);
    });

    it('opens a confirmation dialog before deleting', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.get(`button[aria-label="delete S.40 - Personal Information"]`).click();
        cy.contains('Delete Exemption Template').should('be.visible');
        cy.contains('S.40 - Personal Information').should('be.visible');
    });

    it('deletes a template after confirmation', () => {
        cy.intercept('DELETE', '**/cases/exemptions/1', { statusCode: 204 }).as('deleteTemplate');

        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.get(`button[aria-label="delete S.40 - Personal Information"]`).click();
        cy.get('button').contains('Delete').last().click();
        cy.wait('@deleteTemplate');
    });
});
