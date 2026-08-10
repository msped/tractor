import React from 'react';
import { LoginComponent } from './LoginComponent';

describe('<LoginComponent />', () => {
    it('renders the login form', () => {
        cy.fullMount(<LoginComponent />);
        cy.contains('h1', 'Tractor').should('be.visible');
        cy.get('input[name="username"]').should('be.visible');
        cy.get('input[name="password"]').should('be.visible');
        cy.contains('button', 'Sign in').should('be.visible');
        cy.contains('OR').should('not.exist');
    });

    it('allows typing into username and password fields', () => {
        cy.fullMount(<LoginComponent />);
        cy.get('input[name="username"]').type('testuser').should('have.value', 'testuser');
        cy.get('input[name="password"]').type('password123').should('have.value', 'password123');
    });

    it('shows session expired message when sessionError is SessionExpired', () => {
        cy.fullMount(<LoginComponent sessionError="SessionExpired" />);
        cy.contains('Your session has expired, please log in again.').should('be.visible');
    });

    context('Credentials sign-in', () => {
        const username = 'test.user';
        const password = 'password123';

        it('redirects to /cases on successful sign-in', () => {
            cy.intercept('POST', '**/api/auth/sign-in/username', {
                statusCode: 200,
                body: { token: 'fake-token', user: { id: '1' } },
            }).as('signIn');

            cy.fullMount(<LoginComponent />);
            cy.get('input[name="username"]').type(username);
            cy.get('input[name="password"]').type(password);
            cy.contains('button', 'Sign in').click();

            cy.wait('@signIn');
            cy.get('@router:push').should('have.been.calledWith', '/cases');
        });

        it('shows the credentials message on a genuine 401', () => {
            cy.intercept('POST', '**/api/auth/sign-in/username', {
                statusCode: 401,
                body: { message: 'Invalid username or password.' },
            }).as('signIn');

            cy.fullMount(<LoginComponent />);
            cy.get('input[name="username"]').type('wrong');
            cy.get('input[name="password"]').type('user');
            cy.contains('button', 'Sign in').click();

            cy.contains('Invalid username or password.').should('be.visible');
        });

        it('tells a throttled user to wait rather than to check their password', () => {
            cy.intercept('POST', '**/api/auth/sign-in/username', {
                statusCode: 429,
                body: {
                    message:
                        'Too many sign-in attempts. Please wait a minute and try again.',
                },
            }).as('signIn');

            cy.fullMount(<LoginComponent />);
            cy.get('input[name="username"]').type(username);
            cy.get('input[name="password"]').type(password);
            cy.contains('button', 'Sign in').click();

            cy.contains('Too many sign-in attempts').should('be.visible');
            cy.contains('credentials').should('not.exist');
        });

        it('reports a backend outage as unavailable, not as bad credentials', () => {
            cy.intercept('POST', '**/api/auth/sign-in/username', {
                statusCode: 503,
                body: {
                    message:
                        'Sign-in is temporarily unavailable. Please try again shortly.',
                },
            }).as('signIn');

            cy.fullMount(<LoginComponent />);
            cy.get('input[name="username"]').type(username);
            cy.get('input[name="password"]').type(password);
            cy.contains('button', 'Sign in').click();

            cy.contains('temporarily unavailable').should('be.visible');
            cy.contains('credentials').should('not.exist');
        });

        it('falls back to a generic message when the server sends none', () => {
            cy.intercept('POST', '**/api/auth/sign-in/username', {
                statusCode: 500,
                body: {},
            }).as('signIn');

            cy.fullMount(<LoginComponent />);
            cy.get('input[name="username"]').type(username);
            cy.get('input[name="password"]').type(password);
            cy.contains('button', 'Sign in').click();

            cy.contains('Login failed. Please try again.').should('be.visible');
        });
    });

    context('Social providers', () => {
        const socialProviders = [{ id: 'microsoft', name: 'Microsoft' }];

        it('renders social provider buttons when socialProviders prop is given', () => {
            cy.fullMount(<LoginComponent socialProviders={socialProviders} />);
            cy.contains('OR').should('be.visible');
            cy.contains('button', 'Sign in with Microsoft').should('be.visible');
        });

        it('calls social sign-in with correct provider when button is clicked', () => {
            cy.intercept('POST', '**/api/auth/sign-in/oauth2', {
                statusCode: 200,
                body: { url: 'https://login.microsoftonline.com/...' },
            }).as('socialSignIn');

            cy.fullMount(<LoginComponent socialProviders={socialProviders} />);
            cy.contains('button', 'Sign in with Microsoft').click();

            cy.wait('@socialSignIn').its('request.body').should('deep.include', { providerId: 'microsoft' });
        });
    });
});
