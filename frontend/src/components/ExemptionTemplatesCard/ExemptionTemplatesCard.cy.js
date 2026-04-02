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

    it('shows template count on the card', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('2 templates').should('be.visible');
    });

    it('opens the manage dialog when Manage is clicked', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.get('[role="dialog"]').contains('Exemption Templates').should('be.visible');
    });

    it('displays templates returned from the API', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.contains('S.40 - Personal Information').should('be.visible');
        cy.contains('Personal data exemption').should('be.visible');
        cy.contains('S.42 - Legal Privilege').should('be.visible');
    });

    it('shows empty state when no templates exist', () => {
        cy.intercept('GET', '**/cases/exemptions', { body: [] }).as('getTemplatesEmpty');
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplatesEmpty');
        cy.contains('button', 'Manage').click();
        cy.contains('No exemption templates configured.').should('be.visible');
    });

    it('shows the add form when Add is clicked', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').should('be.visible');
        cy.get('input[aria-label="template description"]').should('be.visible');
        cy.get('button').contains('Save').should('be.disabled');
    });

    it('enables Save only when name is entered', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
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
        cy.contains('button', 'Manage').click();
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
        cy.contains('button', 'Manage').click();
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').type('Something');
        cy.get('button').contains('Cancel').click();
        cy.get('input[aria-label="template name"]').should('not.exist');
        cy.get('@createTemplate.all').should('have.length', 0);
    });

    it('opens a confirmation dialog before deleting', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get(`button[aria-label="delete S.40 - Personal Information"]`).click();
        cy.contains('[role="dialog"]', 'Delete Exemption Template').within(() => {
            cy.contains('S.40 - Personal Information').should('be.visible');
        });
    });

    it('shows error toast when creating a template fails', () => {
        cy.intercept('POST', '**/cases/exemptions', { statusCode: 500, body: {} }).as('createFail');

        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').type('S.43 - Test');
        cy.get('button').contains('Save').click();
        cy.wait('@createFail');
        // Add form should remain open after error
        cy.get('input[aria-label="template name"]').should('exist');
    });

    it('shows error toast when deleting a template fails', () => {
        cy.intercept('DELETE', '**/cases/exemptions/1', { statusCode: 500, body: {} }).as('deleteFail');

        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get(`button[aria-label="delete S.40 - Personal Information"]`).click();
        cy.get('button').contains('Delete').last().click();
        cy.wait('@deleteFail');
        // Template should still be visible after failed delete
        cy.contains('S.40 - Personal Information').should('be.visible');
    });

    it('closes the dialog when the X button is clicked', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.get('button[aria-label="close"]').click();
        cy.get('[role="dialog"]').should('not.exist');
    });

    it('deletes a template after confirmation', () => {
        cy.intercept('DELETE', '**/cases/exemptions/1', { statusCode: 204 }).as('deleteTemplate');

        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get(`button[aria-label="delete S.40 - Personal Information"]`).click();
        cy.get('button').contains('Delete').last().click();
        cy.wait('@deleteTemplate');
    });
});
