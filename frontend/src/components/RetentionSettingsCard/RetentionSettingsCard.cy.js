import React from 'react';
import { SWRConfig } from 'swr';
import { RetentionSettingsCard } from './RetentionSettingsCard';

const mountOpts = { mockSession: { user: { id: '1', name: 'Admin', email: 'admin@example.com', isAdmin: true }, session: { token: 'fake-token', userId: '1' } } };

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

describe('<RetentionSettingsCard />', () => {
    it('renders the card title', () => {
        cy.intercept('GET', '**/cases/settings/retention', {
            body: { auto_case_deletion_enabled: true, retention_warning_days: 30, past: [], upcoming: [] },
        }).as('getRetention');
        cy.fullMount(<TestWrapper><RetentionSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getRetention');
        cy.contains('Auto Case Deletion').should('be.visible');
    });

    it('shows Enabled chip when auto_case_deletion_enabled is true', () => {
        cy.intercept('GET', '**/cases/settings/retention', {
            body: { auto_case_deletion_enabled: true, retention_warning_days: 30, past: [], upcoming: [] },
        }).as('getRetention');
        cy.fullMount(<TestWrapper><RetentionSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getRetention');
        cy.contains('Enabled').should('be.visible');
    });

    it('shows Disabled chip when auto_case_deletion_enabled is false', () => {
        cy.intercept('GET', '**/cases/settings/retention', {
            body: { auto_case_deletion_enabled: false, retention_warning_days: 30, past: [], upcoming: [] },
        }).as('getRetention');
        cy.fullMount(<TestWrapper><RetentionSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getRetention');
        cy.contains('Disabled').should('be.visible');
    });

    it('shows error message when request fails', () => {
        cy.intercept('GET', '**/cases/settings/retention', { statusCode: 500 }).as('getRetentionFail');
        cy.fullMount(<TestWrapper><RetentionSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getRetentionFail');
        cy.contains('Failed to load retention settings.').should('be.visible');
    });
});
