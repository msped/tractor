import React from 'react';
import { TrainingStatusBanner } from './TrainingStatusBanner';

const mountOpts = { mockSession: { user: { id: '1', name: 'Test User', email: 'test@example.com' }, session: { token: 'fake-token', userId: '1' } } };

describe('<TrainingStatusBanner />', () => {
    context('when training is not running', () => {
        it('renders nothing and does not poll', () => {
            cy.intercept('GET', '/api/model-management/status', cy.spy().as('statusSpy'));
            cy.fullMount(<TrainingStatusBanner initialIsRunning={false} pollInterval={100} />, mountOpts);
            cy.get('[role="alert"]').should('not.exist');
            // Idle page must not poll the status endpoint at all.
            cy.wait(350);
            cy.get('@statusSpy').should('not.have.been.called');
        });
    });

    context('when training is running', () => {
        it('shows an info alert with a progress bar', () => {
            cy.intercept('GET', '/api/model-management/status', { body: { is_running: true } });
            cy.fullMount(<TrainingStatusBanner initialIsRunning={true} />, mountOpts);
            cy.get('[role="alert"]').should('be.visible');
            cy.contains('Training is in progress').should('be.visible');
            cy.get('[role="progressbar"]').should('be.visible');
        });

        it('offers a stop control', () => {
            cy.intercept('GET', '/api/model-management/status', { body: { is_running: true } });
            cy.fullMount(<TrainingStatusBanner initialIsRunning={true} />, mountOpts);
            cy.contains('button', 'Stop training').should('be.enabled');
        });

        it('requests a stop and reports that no model will be saved', () => {
            cy.intercept('GET', '/api/model-management/status', { body: { is_running: true } });
            cy.intercept('POST', '/api/model-management/training/stop', {
                body: { status: 'stop requested', dequeued: 0 },
            }).as('stop');
            cy.fullMount(<TrainingStatusBanner initialIsRunning={true} />, mountOpts);

            cy.contains('button', 'Stop training').click();

            cy.wait('@stop');
            // The banner stays up — the run is still unwinding — but says so,
            // and the control is disabled so it cannot be asked twice.
            cy.contains('Stopping training').should('be.visible');
            cy.contains('button', 'Stopping').should('be.disabled');
        });

        it('reflects a stop already requested elsewhere', () => {
            cy.intercept('GET', '/api/model-management/status', {
                body: { is_running: true, stop_requested: true },
            }).as('status');
            cy.fullMount(<TrainingStatusBanner initialIsRunning={true} pollInterval={100} />, mountOpts);

            cy.wait('@status');
            cy.contains('button', 'Stopping').should('be.disabled');
        });

        it('keeps the banner usable when the stop request fails', () => {
            cy.intercept('GET', '/api/model-management/status', { body: { is_running: true } });
            cy.intercept('POST', '/api/model-management/training/stop', {
                statusCode: 500,
                body: { detail: 'boom' },
            }).as('stopFails');
            cy.fullMount(<TrainingStatusBanner initialIsRunning={true} />, mountOpts);

            cy.contains('button', 'Stop training').click();

            cy.wait('@stopFails');
            cy.contains('button', 'Stop training').should('be.enabled');
        });
    });

    context('when training transitions from running to complete', () => {
        it('calls router.refresh() and hides the banner', () => {
            cy.intercept('GET', '/api/model-management/status', { body: { is_running: false } }).as('secondStatus');
            cy.intercept(
                { method: 'GET', url: '/api/model-management/status', times: 1 },
                { body: { is_running: true } }
            ).as('firstStatus');
            cy.fullMount(<TrainingStatusBanner initialIsRunning={true} pollInterval={100} />, mountOpts);
            cy.wait('@firstStatus');
            cy.get('[role="progressbar"]').should('be.visible');
            cy.wait('@secondStatus');
            cy.get('@router:refresh').should('have.been.calledOnce');
            cy.get('[role="alert"]').should('not.exist');
        });
    });
});
