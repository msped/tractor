import React from 'react';
import { SWRConfig } from 'swr';
import { ReviewWorkflowSettingsCard } from './ReviewWorkflowSettingsCard';

const mountOpts = { mockSession: { user: { id: '1', name: 'Test User', email: 'test@example.com' }, session: { token: 'fake-token', userId: '1' } } };

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

describe('<ReviewWorkflowSettingsCard />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/cases/settings/review-workflow', { body: { auto_accept_enabled: false } }).as('getSettings');
    });

    it('renders the card title and Configure button', () => {
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('Review Workflow').should('be.visible');
        cy.contains('button', 'Configure').should('be.visible');
    });

    it('shows Disabled chip when auto-accept is off', () => {
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('Disabled').should('be.visible');
    });

    it('shows Enabled chip when auto-accept is on', () => {
        cy.intercept('GET', '**/cases/settings/review-workflow', { body: { auto_accept_enabled: true } }).as('getSettingsEnabled');
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettingsEnabled');
        cy.contains('Enabled').should('be.visible');
    });

    it('opens the configure dialog when Configure is clicked', () => {
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('button', 'Configure').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.get('[role="dialog"]').contains('Review Workflow Settings').should('be.visible');
    });

    it('shows the auto-accept toggle in the dialog', () => {
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('button', 'Configure').click();
        cy.contains('Enable auto-accept mode').should('be.visible');
    });

    it('toggle reflects current setting when dialog opens', () => {
        cy.intercept('GET', '**/cases/settings/review-workflow', { body: { auto_accept_enabled: true } }).as('getSettingsOn');
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettingsOn');
        cy.contains('button', 'Configure').click();
        cy.get('input[type="checkbox"]').should('be.checked');
    });

    it('calls PATCH with correct payload when saving', () => {
        cy.intercept('PATCH', '**/cases/settings/review-workflow', { body: { auto_accept_enabled: true } }).as('patchSettings');
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('button', 'Configure').click();
        cy.get('input[type="checkbox"]').click({ force: true });
        cy.contains('button', 'Save').click();
        cy.wait('@patchSettings').its('request.body').should('deep.equal', { auto_accept_enabled: true });
    });

    it('closes the dialog after a successful save', () => {
        cy.intercept('PATCH', '**/cases/settings/review-workflow', { body: { auto_accept_enabled: false } }).as('patchSettings');
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('button', 'Configure').click();
        cy.contains('button', 'Save').click();
        cy.wait('@patchSettings');
        cy.get('[role="dialog"]').should('not.exist');
    });

    it('resets the toggle to the saved value when Cancel is clicked', () => {
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('button', 'Configure').click();
        cy.get('input[type="checkbox"]').click({ force: true });
        cy.get('input[type="checkbox"]').should('be.checked');
        cy.contains('button', 'Cancel').click();
        cy.get('[role="dialog"]').should('not.exist');
        cy.contains('button', 'Configure').click();
        cy.get('input[type="checkbox"]').should('not.be.checked');
    });

    it('shows error toast when save fails', () => {
        cy.intercept('PATCH', '**/cases/settings/review-workflow', { statusCode: 500, body: {} }).as('patchFail');
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('button', 'Configure').click();
        cy.contains('button', 'Save').click();
        cy.wait('@patchFail');
        cy.contains('Failed to update review workflow settings.').should('be.visible');
    });

    it('shows error message when GET fails', () => {
        cy.intercept('GET', '**/cases/settings/review-workflow', { statusCode: 500, body: {} }).as('getSettingsError');
        cy.fullMount(<TestWrapper><ReviewWorkflowSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettingsError');
        cy.contains('Failed to load review workflow settings.').should('be.visible');
    });
});
