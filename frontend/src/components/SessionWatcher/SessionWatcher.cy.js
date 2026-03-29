import React from 'react';
import { SessionWatcher } from './SessionWatcher';

const validSession = { access_token: 'fake-token', user: { name: 'Test User' } };

describe('<SessionWatcher />', () => {
    context('when session is valid', () => {
        it('does not redirect or sign out', () => {
            const signOutStub = cy.stub().resolves().as('signOut');
            cy.fullMount(
                <SessionWatcher signOut={signOutStub} />,
                { mockSession: validSession }
            );
            cy.get('@router:push').should('not.have.been.called');
            cy.get('@signOut').should('not.have.been.called');
        });

        it('renders no visible UI', () => {
            const signOutStub = cy.stub().resolves();
            cy.fullMount(
                <SessionWatcher signOut={signOutStub} />,
                { mockSession: validSession }
            );
            cy.get('[data-testid]').should('not.exist');
        });
    });

    context('when session has RefreshTokenError', () => {
        it('calls signOut with redirect: false', () => {
            const signOutStub = cy.stub().resolves().as('signOut');
            cy.fullMount(
                <SessionWatcher signOut={signOutStub} />,
                { mockSession: { ...validSession, error: 'RefreshTokenError' } }
            );
            cy.get('@signOut').should('have.been.calledOnce');
            cy.get('@signOut').should('have.been.calledWith', { redirect: false });
        });

        it('redirects to /?error=SessionExpired', () => {
            const signOutStub = cy.stub().resolves().as('signOut');
            cy.fullMount(
                <SessionWatcher signOut={signOutStub} />,
                { mockSession: { ...validSession, error: 'RefreshTokenError' } }
            );
            cy.get('@router:push').should('have.been.calledWith', '/?error=SessionExpired');
        });
    });

    context('when session is unauthenticated', () => {
        it('calls signOut with redirect: false', () => {
            const signOutStub = cy.stub().resolves().as('signOut');
            cy.fullMount(
                <SessionWatcher signOut={signOutStub} />,
                { mockSession: null }
            );
            cy.get('@signOut').should('have.been.calledOnce');
            cy.get('@signOut').should('have.been.calledWith', { redirect: false });
        });

        it('redirects to /?error=SessionExpired', () => {
            const signOutStub = cy.stub().resolves().as('signOut');
            cy.fullMount(
                <SessionWatcher signOut={signOutStub} />,
                { mockSession: null }
            );
            cy.get('@router:push').should('have.been.calledWith', '/?error=SessionExpired');
        });
    });

    context('session polling interval', () => {
        it('does not redirect before the interval fires with a valid session', () => {
            cy.clock();
            const signOutStub = cy.stub().resolves().as('signOut');
            cy.fullMount(
                <SessionWatcher signOut={signOutStub} checkInterval={1000} />,
                { mockSession: validSession }
            );
            cy.tick(500);
            cy.get('@router:push').should('not.have.been.called');
        });

        it('does not redirect after the interval fires with a valid session', () => {
            cy.clock();
            const signOutStub = cy.stub().resolves().as('signOut');
            cy.fullMount(
                <SessionWatcher signOut={signOutStub} checkInterval={1000} />,
                { mockSession: validSession }
            );
            cy.tick(1000);
            cy.get('@router:push').should('not.have.been.called');
        });
    });
});
