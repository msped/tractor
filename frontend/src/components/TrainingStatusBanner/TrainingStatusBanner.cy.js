import React from 'react';
import { TrainingStatusBanner } from './TrainingStatusBanner';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

describe('<TrainingStatusBanner />', () => {
    context('when training is not running', () => {
        it('renders nothing', () => {
            cy.intercept('GET', '/api/training/status', { body: { is_running: false } });
            cy.fullMount(<TrainingStatusBanner />, mountOpts);
            cy.get('[role="alert"]').should('not.exist');
        });
    });

    context('when training is running', () => {
        it('shows an info alert with a progress bar', () => {
            cy.intercept('GET', '/api/training/status', { body: { is_running: true } });
            cy.fullMount(<TrainingStatusBanner />, mountOpts);
            cy.get('[role="alert"]').should('be.visible');
            cy.contains('Training is in progress').should('be.visible');
            cy.get('[role="progressbar"]').should('be.visible');
        });
    });

    context('when training transitions from running to complete', () => {
        it('calls router.refresh() and hides the banner', () => {
            cy.intercept('GET', '/api/training/status', { body: { is_running: false } }).as('secondStatus');
            cy.intercept(
                { method: 'GET', url: '/api/training/status', times: 1 },
                { body: { is_running: true } }
            ).as('firstStatus');
            cy.fullMount(<TrainingStatusBanner pollInterval={100} />, mountOpts);
            cy.wait('@firstStatus');
            cy.get('[role="progressbar"]').should('be.visible');
            cy.wait('@secondStatus');
            cy.get('@router:refresh').should('have.been.calledOnce');
            cy.get('[role="alert"]').should('not.exist');
        });
    });

    context('when not authenticated', () => {
        it('does not show the banner when there is no access token', () => {
            cy.intercept('GET', '/api/training/status', { body: { is_running: true } }).as('statusRequest');
            cy.fullMount(<TrainingStatusBanner />, { mockSession: null });
            cy.get('[role="alert"]').should('not.exist');
        });
    });
});
