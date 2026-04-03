import React from 'react';
import { SWRConfig } from 'swr';
import { ApiKeysCard } from './ApiKeysCard';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

const mockKeys = [
    {
        id: 1,
        description: 'Case management integration',
        created_at: '2026-01-15T10:00:00Z',
        created_by_username: 'admin',
    },
    {
        id: 2,
        description: 'Custom workflow tool',
        created_at: '2026-02-20T14:30:00Z',
        created_by_username: 'admin',
    },
];

describe('<ApiKeysCard />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/auth/api-keys', { body: mockKeys }).as('getKeys');
    });

    it('renders the card title and description', () => {
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('API Keys').should('be.visible');
        cy.contains('Allow external services').should('be.visible');
    });

    it('shows active key count on the card', () => {
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('2 active keys').should('be.visible');
    });

    it('shows singular "key" for one key', () => {
        cy.intercept('GET', '**/auth/api-keys', { body: [mockKeys[0]] }).as('getSingleKey');
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getSingleKey');
        cy.contains('1 active key').should('be.visible');
    });

    it('opens the manage dialog when Manage is clicked', () => {
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.get('[role="dialog"]').contains('API Keys').should('be.visible');
    });

    it('displays keys returned from the API', () => {
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.contains('Case management integration').should('be.visible');
        cy.contains('Custom workflow tool').should('be.visible');
    });

    it('shows empty state when no keys exist', () => {
        cy.intercept('GET', '**/auth/api-keys', { body: [] }).as('getKeysEmpty');
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeysEmpty');
        cy.contains('button', 'Manage').click();
        cy.contains('No API keys configured.').should('be.visible');
    });

    it('shows the generate form when Generate Key is clicked', () => {
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Generate Key').click();
        cy.get('input[aria-label="key description"]').should('be.visible');
        cy.get('button[type="submit"]').should('be.disabled');
    });

    it('enables Generate only when description is entered', () => {
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Generate Key').click();
        cy.get('button[type="submit"]').should('be.disabled');
        cy.get('input[aria-label="key description"]').type('My integration');
        cy.get('button[type="submit"]').should('be.enabled');
    });

    it('submits the new key and displays the one-time key alert', () => {
        cy.intercept('POST', '**/auth/api-keys', {
            statusCode: 201,
            body: {
                id: 3,
                description: 'My integration',
                created_at: '2026-04-03T12:00:00Z',
                created_by_username: 'admin',
                key: 'abc123secretkey',
            },
        }).as('createKey');

        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Generate Key').click();
        cy.get('input[aria-label="key description"]').type('My integration');
        cy.get('button[type="submit"]').click();
        cy.wait('@createKey');
        cy.get('[aria-label="generated api key"]').should('contain.text', 'abc123secretkey');
        cy.contains('Copy this key now').should('be.visible');
        cy.get('input[aria-label="key description"]').should('not.exist');
    });

    it('cancels the generate form without submitting', () => {
        cy.intercept('POST', '**/auth/api-keys').as('createKey');

        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Generate Key').click();
        cy.get('input[aria-label="key description"]').type('Something');
        cy.contains('button', 'Cancel').click();
        cy.get('input[aria-label="key description"]').should('not.exist');
        cy.get('@createKey.all').should('have.length', 0);
    });

    it('clears the one-time key when the dialog is closed', () => {
        cy.intercept('POST', '**/auth/api-keys', {
            statusCode: 201,
            body: {
                id: 3,
                description: 'My integration',
                created_at: '2026-04-03T12:00:00Z',
                created_by_username: 'admin',
                key: 'abc123secretkey',
            },
        }).as('createKey');

        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Generate Key').click();
        cy.get('input[aria-label="key description"]').type('My integration');
        cy.get('button[type="submit"]').click();
        cy.wait('@createKey');
        cy.get('button[aria-label="close"]').click();
        cy.contains('button', 'Manage').click();
        cy.contains('Copy this key now').should('not.exist');
    });

    it('opens a confirmation dialog before revoking a key', () => {
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.get('button[aria-label="revoke Case management integration"]').click();
        cy.contains('[role="dialog"]', 'Revoke API Key').within(() => {
            cy.contains('Case management integration').should('be.visible');
        });
    });

    it('revokes a key after confirmation', () => {
        cy.intercept('DELETE', '**/auth/api-keys/1', { statusCode: 204 }).as('revokeKey');

        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.get('button[aria-label="revoke Case management integration"]').click();
        cy.contains('button', 'Revoke').last().click();
        cy.wait('@revokeKey');
    });

    it('closes the dialog when the X button is clicked', () => {
        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.get('button[aria-label="close"]').click();
        cy.get('[role="dialog"]').should('not.exist');
    });

    it('shows error toast when creating a key fails', () => {
        cy.intercept('POST', '**/auth/api-keys', { statusCode: 500, body: {} }).as('createFail');

        cy.fullMount(<TestWrapper><ApiKeysCard /></TestWrapper>, mountOpts);
        cy.wait('@getKeys');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Generate Key').click();
        cy.get('input[aria-label="key description"]').type('My integration');
        cy.get('button[type="submit"]').click();
        cy.wait('@createFail');
        cy.get('input[aria-label="key description"]').should('exist');
    });
});
