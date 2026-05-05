import React from 'react';
import { TrainingSettingsCard } from './TrainingSettingsCard';

describe('<TrainingSettingsCard />', () => {
    beforeEach(() => {
        cy.fullMount(<TrainingSettingsCard />, { mockSession: { user: { id: '1', name: 'Test User', email: 'test@example.com' }, session: { token: 'fake-token', userId: '1' } } });
    });

    it('should render the card content correctly', () => {
        cy.get('[data-testid="ModelTrainingIcon"]').should('be.visible');
        cy.contains('h2', 'Model Training').should('be.visible');

        cy.contains('Manage manual and scheduled training runs to improve model performance over time.').should('be.visible');
        cy.contains('a', 'Go to Model Management')
            .should('be.visible')
            .and('have.attr', 'href', '/model-management');
    });
});