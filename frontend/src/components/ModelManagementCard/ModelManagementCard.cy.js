import React from 'react';
import { SWRConfig } from 'swr';
import { ModelManagementCard } from './ModelManagementCard';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

// Wrapper to disable SWR cache for testing
const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

const mockModels = [
    {
        id: 'model-1',
        name: 'Redaction Model v1',
        is_active: true,
        created_at: '2024-01-15T10:30:00Z',
    },
    {
        id: 'model-2',
        name: 'Redaction Model v2',
        is_active: false,
        created_at: '2024-02-20T14:45:00Z',
    },
    {
        id: 'model-3',
        name: 'Redaction Model v3',
        is_active: false,
        created_at: '2024-03-10T09:00:00Z',
    },
];

describe('<ModelManagementCard />', () => {
    context('Loading State', () => {
        it('shows loading spinner while fetching models', () => {
            cy.intercept('GET', '**/models', {
                delay: 500,
                body: mockModels,
            }).as('getModels');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.get('[role="progressbar"]').should('be.visible');
        });
    });

    context('Error State', () => {
        it('shows error alert when fetching models fails', () => {
            cy.intercept('GET', '**/models', {
                statusCode: 500,
                body: { detail: 'Server error' },
            }).as('getModelsFailed');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModelsFailed');
            cy.get('[role="alert"]').should('be.visible');
        });
    });

    context('Empty State', () => {
        it('shows message when no models are found', () => {
            cy.intercept('GET', '**/models', { body: [] }).as('getModelsEmpty');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModelsEmpty');
            cy.contains('No trained models found.').should('be.visible');
        });
    });

    context('With Models', () => {
        beforeEach(() => {
            cy.intercept('GET', '**/models', { body: mockModels }).as('getModels');
        });

        it('renders the card with title and description', () => {
            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('h2', 'Active Redaction Model').should('be.visible');
            cy.contains('Select the model to be used for suggesting redactions').should('be.visible');
        });

        it('displays all models in the list', () => {
            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('Redaction Model v1').should('be.visible');
            cy.contains('Redaction Model v2').should('be.visible');
            cy.contains('Redaction Model v3').should('be.visible');
        });

        it('shows "Active" chip for the active model', () => {
            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v1').within(() => {
                cy.contains('Active').should('be.visible');
            });
        });

        it('does not show "Active" chip for inactive models', () => {
            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v2').within(() => {
                cy.contains('span', 'Active').should('not.exist');
            });
        });

        it('displays created date for each model', () => {
            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('Created:').should('be.visible');
        });

        it('disables "Set Active" button for the active model', () => {
            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v1')
                .contains('button', 'Set Active')
                .should('be.disabled');
        });

        it('enables "Set Active" button for inactive models', () => {
            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v2')
                .contains('button', 'Set Active')
                .should('not.be.disabled');
        });
    });

    context('Set Active Model', () => {
        beforeEach(() => {
            cy.intercept('GET', '**/models', { body: mockModels }).as('getModels');
        });

        it('calls setActiveModel API when clicking "Set Active"', () => {
            cy.intercept('POST', '**/models/model-2/set-active', {
                statusCode: 200,
                body: {},
            }).as('setActive');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v2')
                .contains('button', 'Set Active')
                .click();

            cy.wait('@setActive');
        });

        it('shows loading spinner on button while activating', () => {
            cy.intercept('POST', '**/models/model-2/set-active', {
                delay: 500,
                statusCode: 200,
                body: {},
            }).as('setActive');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v2')
                .contains('button', 'Set Active')
                .click();

            cy.contains('li', 'Redaction Model v2')
                .find('button')
                .find('[role="progressbar"]')
                .should('be.visible');
        });

        it('shows success toast when model is activated', () => {
            cy.intercept('POST', '**/models/model-2/set-active', {
                statusCode: 200,
                body: {},
            }).as('setActive');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v2')
                .contains('button', 'Set Active')
                .click();

            cy.wait('@setActive');
            cy.contains('Model activated successfully!').should('be.visible');
        });

        it('shows error toast when activation fails', () => {
            cy.intercept('POST', '**/models/model-2/set-active', {
                statusCode: 500,
                body: { detail: 'Failed to set active model.' },
            }).as('setActiveFailed');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v2')
                .contains('button', 'Set Active')
                .click();

            cy.wait('@setActiveFailed');
            cy.contains('Failed to set active model.').should('be.visible');
        });

        it('disables all "Set Active" buttons while one is submitting', () => {
            cy.intercept('POST', '**/models/model-2/set-active', {
                delay: 1000,
                statusCode: 200,
                body: {},
            }).as('setActive');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModels');
            cy.contains('li', 'Redaction Model v2')
                .contains('button', 'Set Active')
                .click();

            cy.contains('li', 'Redaction Model v3')
                .contains('button', 'Set Active')
                .should('be.disabled');
        });

        it('re-enables buttons after activation completes', () => {
            const updatedModels = mockModels.map(m => ({
                ...m,
                is_active: m.id === 'model-2',
            }));

            cy.intercept('GET', '**/models', { body: mockModels }).as('getModelsInitial');

            cy.intercept('POST', '**/models/model-2/set-active', {
                statusCode: 200,
                body: {},
            }).as('setActive');

            cy.fullMount(
                <TestWrapper>
                    <ModelManagementCard />
                </TestWrapper>,
                mountOpts
            );

            cy.wait('@getModelsInitial');

            cy.intercept('GET', '**/models', { body: updatedModels }).as('getModelsRefresh');

            cy.contains('li', 'Redaction Model v2')
                .contains('button', 'Set Active')
                .click();

            cy.wait('@setActive');
            cy.wait('@getModelsRefresh');

            cy.contains('li', 'Redaction Model v2')
                .contains('button', 'Set Active')
                .should('be.disabled');

            cy.contains('li', 'Redaction Model v3')
                .contains('button', 'Set Active')
                .should('not.be.disabled');
        });
    });
});
