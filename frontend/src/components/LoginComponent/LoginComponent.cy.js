import React from 'react';
import { LoginComponent } from './LoginComponent';
import * as NextAuth from 'next-auth/react';

describe('<LoginComponent />', () => {
    beforeEach(() => {
    cy.intercept('GET', '/api/auth/providers', { body: {} });
  });


  it('should render the login form correctly', () => {
    cy.mount(<LoginComponent />);
    cy.contains('h1', 'Tractor').should('be.visible');
    cy.get('input[name="username"]').should('be.visible');
    cy.get('input[name="password"]').should('be.visible');
    cy.contains('button', 'Login').should('be.visible');
    cy.contains('OR').should('not.exist');
  });

  it('should allow typing into username and password fields', () => {
    cy.mount(<LoginComponent />);
    cy.get('input[name="username"]').type('testuser').should('have.value', 'testuser');
    cy.get('input[name="password"]').type('password123').should('have.value', 'password123');
  });

  context('Form Submission', () => {
    const username = 'test.user';
    const password = 'password123';

    it('should call signIn with correct credentials on submission', () => {
      // Stub signIn to resolve successfully
      const signInStub = cy.stub(
        require('next-auth/react'),
        'signIn'
      ).resolves({ ok: true, error: null }).as('signInStub');

      cy.mount(<LoginComponent signIn={signInStub}/>);

      cy.get('input[name="username"]').type(username);
      cy.get('input[name="password"]').type(password);
      cy.contains('button', 'Login').click();

      cy.get('@signInStub').should('have.been.calledOnce');
      cy.get('@signInStub').should('have.been.calledWith',
        'credentials',
        {
          username,
          password,
          redirect: true,
          callbackUrl: '/cases'
        }
      );
      cy.contains('Login failed').should('not.exist');
    });

    it('should display an error message on failed login', () => {
      // Stub signIn to resolve with an error
      const signInStub = cy.stub(NextAuth, 'signIn').resolves({ ok: false, error: 'Invalid credentials' }).as('signInStub');

      cy.mount(<LoginComponent signIn={signInStub} />);

      cy.get('input[name="username"]').type('wrong');
      cy.get('input[name="password"]').type('user');
      cy.contains('button', 'Login').click();

      cy.contains('Login failed. Please check your credentials.').should('be.visible');
    });
  });

  it('should render external provider buttons and trigger signIn', () => {
    const providers = {
      "microsoft-entra-id": {
        id: "microsoft-entra-id",
        name: "Microsoft",
        type: "oauth",
        signinUrl: "http://localhost:3000/api/auth/signin/microsoft-entra-id",
        callbackUrl: "http://localhost:3000/api/auth/callback/microsoft-entra-id"
      }
    };
    cy.intercept('GET', '/api/auth/providers', { body: providers }).as('getProviders');
    const signInStub = cy.stub().resolves({ ok: true }).as('signInStub');

    cy.mount(<LoginComponent signIn={signInStub} />);
    cy.wait('@getProviders');

    cy.contains('OR').should('be.visible');
    cy.contains('button', 'Sign in with Microsoft').should('be.visible').click();
    cy.get('@signInStub').should('have.been.calledWith', 'microsoft-entra-id', { callbackUrl: '/cases' });
  });
});