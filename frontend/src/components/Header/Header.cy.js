import React from 'react';
import { Header } from './Header';
import * as NextAuth from 'next-auth/react';
import { SessionProvider } from 'next-auth/react';

describe('<Header />', () => {
  context('When user is not authenticated', () => {
    beforeEach(() => {
      cy.stub(NextAuth, 'useSession').returns({
        data: null,
        status: 'unauthenticated',
      });
      cy.mount(<SessionProvider session={null}><Header /></SessionProvider>);
    });

    it('should display the app name and a sign-in button', () => {
      cy.contains('a', 'SAM').should('be.visible').and('have.attr', 'href', '/');
      cy.contains('a', 'Sign In').should('be.visible');
    });

    it('should not display user-specific links like Cases or Settings', () => {
      cy.contains('a', 'Cases').should('not.exist');
      cy.get('a[href="/settings"]').should('not.exist');
      cy.contains('button', 'Sign Out').should('not.exist');
    });
  });

  context('When user is authenticated', () => {
    const mockSession = {
      user: { username: 'test.user' },
    };

    beforeEach(() => {
      cy.stub(NextAuth, 'useSession').returns({
        data: mockSession,
        status: 'authenticated',
      });
      cy.mount(<SessionProvider session={mockSession}><Header /></SessionProvider>);
    });

    it('should display the app name, cases link, and user info', () => {
      cy.contains('a', 'SAM').should('be.visible');
      cy.contains('a', 'Cases').should('be.visible').and('have.attr', 'href', '/cases');
      cy.contains(mockSession.user.username).should('be.visible');
    });

    it('should display the settings and sign-out buttons', () => {
      cy.get('a[href="/settings"]').should('be.visible');
      cy.contains('button', 'Sign Out').should('be.visible');
      cy.contains('button', 'Sign In').should('not.exist');
    });
  });
});