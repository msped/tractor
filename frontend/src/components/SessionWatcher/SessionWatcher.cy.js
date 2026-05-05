import React from 'react';
import { SessionWatcher } from './SessionWatcher';

const validSession = {
    user: { id: '1', name: 'Test User', email: 'test@example.com' },
    session: { token: 'fake-token', userId: '1' },
};

describe('<SessionWatcher />', () => {
    context('when session is valid', () => {
        it('does not redirect', () => {
            cy.fullMount(<SessionWatcher />, { mockSession: validSession });
            cy.get('@router:push').should('not.have.been.called');
        });

        it('renders no visible UI', () => {
            cy.fullMount(<SessionWatcher />, { mockSession: validSession });
            cy.get('[data-testid]').should('not.exist');
        });
    });

    context('when session is null (unauthenticated)', () => {
        it('redirects to /', () => {
            cy.fullMount(<SessionWatcher />, { mockSession: null });
            cy.get('@router:push').should('have.been.calledWith', '/');
        });
    });
});
