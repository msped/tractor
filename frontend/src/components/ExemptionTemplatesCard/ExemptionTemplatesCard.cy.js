import React from 'react';
import { SWRConfig } from 'swr';
import { ExemptionTemplatesCard } from './ExemptionTemplatesCard';

const mountOpts = { mockSession: { user: { id: '1', name: 'Test User', email: 'test@example.com' }, session: { token: 'fake-token', userId: '1' } } };

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

const mockTemplates = [
    { id: 1, name: 'S.31 - Law Enforcement', description: 'Law enforcement exemption', trainable: false },
    { id: 2, name: 'S.42 - Legal Privilege', description: '', trainable: true },
];

describe('<ExemptionTemplatesCard />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/cases/exemptions', { body: mockTemplates }).as('getTemplates');
    });

    it('renders the card title and description', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('Exemption Templates').should('be.visible');
        cy.contains('Bases reviewers can withhold Operational Data under').should('be.visible');
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
        cy.contains('S.31 - Law Enforcement').should('be.visible');
        cy.contains('Law enforcement exemption').should('be.visible');
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
        cy.get(`button[aria-label="delete S.31 - Law Enforcement"]`).click();
        cy.contains('[role="dialog"]', 'Delete Exemption Template').within(() => {
            cy.contains('S.31 - Law Enforcement').should('be.visible');
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
        cy.get(`button[aria-label="delete S.31 - Law Enforcement"]`).click();
        cy.get('button').contains('Delete').last().click();
        cy.wait('@deleteFail');
        // Template should still be visible after failed delete
        cy.contains('S.31 - Law Enforcement').should('be.visible');
    });

    it('closes the dialog when the X button is clicked', () => {
        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.get('button[aria-label="close"]').click();
        cy.get('[role="dialog"]').should('not.exist');
    });

    context('Trains the model toggle', () => {
        const toggleFor = (name) => cy.get(`input[aria-label="${name} trains the model"]`);

        it('shows each template\'s current setting and explains it', () => {
            cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
            cy.wait('@getTemplates');
            cy.contains('button', 'Manage').click();
            cy.get('[role="dialog"]').contains('teaches the model').should('be.visible');
            toggleFor('S.31 - Law Enforcement').should('not.be.checked');
            toggleFor('S.42 - Legal Privilege').should('be.checked');
        });

        it('saves a change to the template', () => {
            cy.intercept('PATCH', '**/cases/exemptions/1', {
                body: { ...mockTemplates[0], trainable: true },
            }).as('updateTemplate');
            cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
            cy.wait('@getTemplates');
            cy.contains('button', 'Manage').click();
            cy.intercept('GET', '**/cases/exemptions', {
                body: [{ ...mockTemplates[0], trainable: true }, mockTemplates[1]],
            }).as('refetchTemplates');

            toggleFor('S.31 - Law Enforcement').click();

            cy.wait('@updateTemplate').its('request.body').should('deep.equal', { trainable: true });
            cy.wait('@refetchTemplates');
            toggleFor('S.31 - Law Enforcement').should('be.checked');
        });

        it('keeps the setting when saving fails', () => {
            cy.intercept('PATCH', '**/cases/exemptions/2', { statusCode: 500, body: {} }).as('updateFail');
            cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
            cy.wait('@getTemplates');
            cy.contains('button', 'Manage').click();

            toggleFor('S.42 - Legal Privilege').click();

            cy.wait('@updateFail');
            toggleFor('S.42 - Legal Privilege').should('be.checked');
        });
    });

    context('Deleting a template in use', () => {
        const inUseMessage = '"S.31 - Law Enforcement" is used by 2 redactions, so it can\'t be deleted. Deactivate it to hide it from reviewers; existing redactions keep it.';

        const attemptDelete = () => {
            cy.intercept('DELETE', '**/cases/exemptions/1', { statusCode: 409, body: { detail: inUseMessage, in_use: 2 } }).as('deleteInUse');
            cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
            cy.wait('@getTemplates');
            cy.contains('button', 'Manage').click();
            cy.get('button[aria-label="delete S.31 - Law Enforcement"]').click();
            cy.get('button').contains('Delete').last().click();
            cy.wait('@deleteInUse');
        };

        it('explains the template is in use and offers to deactivate it instead', () => {
            attemptDelete();
            cy.contains('[role="dialog"]', 'Template in use').within(() => {
                cy.contains('is used by 2 redactions').should('be.visible');
                cy.contains('button', 'Deactivate').should('be.visible');
            });
        });

        it('deactivates the template, which leaves the list', () => {
            cy.intercept('PATCH', '**/cases/exemptions/1', { body: { ...mockTemplates[0], is_active: false } }).as('deactivate');
            attemptDelete();
            cy.intercept('GET', '**/cases/exemptions', { body: [mockTemplates[1]] }).as('refetchTemplates');

            cy.contains('[role="dialog"]', 'Template in use').contains('button', 'Deactivate').click();

            cy.wait('@deactivate').its('request.body').should('deep.equal', { is_active: false });
            cy.wait('@refetchTemplates');
            cy.contains('Template in use').should('not.exist');
            cy.contains('S.31 - Law Enforcement').should('not.exist');
            cy.contains('S.42 - Legal Privilege').should('be.visible');
        });

        it('leaves the template alone on cancel', () => {
            cy.intercept('PATCH', '**/cases/exemptions/1').as('deactivate');
            attemptDelete();

            cy.contains('[role="dialog"]', 'Template in use').contains('button', 'Cancel').click();

            cy.contains('Template in use').should('not.exist');
            cy.get('@deactivate.all').should('have.length', 0);
            cy.contains('S.31 - Law Enforcement').should('be.visible');
        });
    });

    it('deletes a template after confirmation', () => {
        cy.intercept('DELETE', '**/cases/exemptions/1', { statusCode: 204 }).as('deleteTemplate');

        cy.fullMount(<TestWrapper><ExemptionTemplatesCard /></TestWrapper>, mountOpts);
        cy.wait('@getTemplates');
        cy.contains('button', 'Manage').click();
        cy.get(`button[aria-label="delete S.31 - Law Enforcement"]`).click();
        cy.get('button').contains('Delete').last().click();
        cy.wait('@deleteTemplate');
    });
});
