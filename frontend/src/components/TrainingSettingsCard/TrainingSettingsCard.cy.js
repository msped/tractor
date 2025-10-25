import React from 'react';
import { TrainingSettingsCard } from './TrainingSettingsCard';

describe('<TrainingSettingsCard />', () => {
    beforeEach(() => {
        cy.fullMount(<TrainingSettingsCard />, { mockSession: { access_token: 'fake-token'}});
    });

    it('should render the card content correctly', () => {
        cy.get('[data-testid="ModelTrainingIcon"]').should('be.visible');
        cy.contains('h2', 'Model Training').should('be.visible');

        cy.contains('Manage manual and scheduled training runs to improve model performance over time.').should('be.visible');
        cy.contains('a', 'Go to Training')
            .should('be.visible')
            .and('have.attr', 'href', '/settings/training');
    });
});