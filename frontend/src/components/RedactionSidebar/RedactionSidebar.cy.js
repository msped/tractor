import React from 'react';
import { RedactionSidebar } from './RedactionSidebar';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

describe('<RedactionSidebar />', () => {
    const mockRedactions = {
        pending: [
            { id: 'p1', text: 'pending text', redaction_type: 'PII', is_suggestion: true },
        ],
        accepted: [
            { id: 'a1', text: 'accepted text', redaction_type: 'OP_DATA', is_suggestion: false, context: null },
            { id: 'a2', text: 'accepted with context', redaction_type: 'DS_INFO', is_suggestion: false, context: { text: 'This is existing context.' } },
        ],
        rejected: [
            { id: 'r1', text: 'rejected text', redaction_type: 'PII', is_suggestion: true, justification: 'Not relevant' },
        ],
        manual: [
            { id: 'm1', text: 'manual text', redaction_type: 'DS_INFO', is_suggestion: false },
        ],
    };

    let baseProps;

    beforeEach(() => {
        baseProps = {
            onAccept: cy.stub().as('onAccept'),
            onReject: cy.stub().as('onReject'),
            onRemove: cy.stub().as('onRemove'),
            onChangeTypeAndAccept: cy.stub().as('onChangeTypeAndAccept'),
            onSuggestionMouseEnter: cy.stub().as('onSuggestionMouseEnter'),
            onSuggestionMouseLeave: cy.stub().as('onSuggestionMouseLeave'),
            scrollToId: null,
            removeScrollId: cy.stub().as('removeScrollId'),
            onContextSave: cy.stub().as('onContextSave'),
        };
    });

    it('renders empty state when no redactions are provided', () => {
        const emptyRedactions = { pending: [], accepted: [], rejected: [], manual: [] };
        cy.fullMount(<RedactionSidebar {...baseProps} redactions={emptyRedactions} />, mountOpts);
        cy.contains('No redactions or suggestions yet.').should('be.visible');
    });

    context('Rendering with redactions', () => {
        beforeEach(() => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} />, mountOpts);
        });

        it('renders all redaction sections with correct counts', () => {
            cy.contains('pending (1)').should('be.visible');
            cy.contains('accepted (2)').should('be.visible');
            cy.contains('rejected (1)').should('be.visible');
            cy.contains('manual (1)').should('be.visible');
        });

        it('expands the "pending" section by default and others are collapsed', () => {
            cy.contains('pending (1)').parents('.MuiAccordion-root').should('be.have.class', 'Mui-expanded');
            cy.contains('accepted (2)').parents('.MuiAccordion-root').should('not.have.class', 'Mui-expanded');
        });

        it('renders redaction item details correctly', () => {
            cy.contains('pending (1)').click();
            cy.contains('li', 'pending text').within(() => {
                cy.contains('"pending text"').should('be.visible');
                cy.contains('Third-Party PII').should('be.visible');
                cy.contains('Source: AI').should('be.visible');
            });

            cy.contains('rejected (1)').click();
            cy.contains('li', 'rejected text').within(() => {
                cy.contains('Reason for rejection: Not relevant').should('be.visible');
            });
        });

        it('renders correct buttons for the "pending" section', () => {
            cy.contains('pending (1)').click();
            cy.contains('li', 'pending text').within(() => {
                cy.contains('button', 'Reject').should('be.visible');
                cy.contains('button', 'Accept').should('be.visible');
            });
        });

        it('renders correct buttons for the "accepted" section', () => {
            cy.contains('accepted (2)').click();
            cy.contains('li', '"accepted text"').contains('button', 'Remove').should('be.visible');
        });

        it('renders correct buttons for the "rejected" section', () => {
            cy.contains('rejected (1)').click();
            cy.contains('li', 'rejected text').contains('button', 'Re-evaluate').should('be.visible');
        });

        it('renders correct buttons for the "manual" section', () => {
            cy.contains('manual (1)').click();
            cy.contains('li', 'manual text').contains('button', 'Remove').should('be.visible');
        });
    });

    context('User Interactions', () => {
        beforeEach(() => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} />, mountOpts);
        });

        it('calls onAccept when "Accept" is clicked', () => {
            cy.contains('li', 'pending text').contains('button', 'Accept').click();
            cy.get('@onAccept').should('have.been.calledOnceWith', 'p1');
        });

        it('calls onReject when "Reject" is clicked', () => {
            cy.contains('li', 'pending text').contains('button', 'Reject').click();
            cy.get('@onReject').should('have.been.calledOnceWith', mockRedactions.pending[0]);
        });

        it('calls onRemove for an accepted item', () => {
            cy.contains('accepted (2)').click();
            cy.contains('li', '"accepted text"').contains('button', 'Remove').click();
            cy.get('@onRemove').should('have.been.calledOnceWith', 'a1');
        });

        it('calls onRemove for a rejected item (Re-evaluate)', () => {
            cy.contains('rejected (1)').click();
            cy.contains('li', 'rejected text').contains('button', 'Re-evaluate').click();
            cy.get('@onRemove').should('have.been.calledOnceWith', 'r1');
        });
    });

    context('Change Type and Accept Menu', () => {
        beforeEach(() => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} />, mountOpts);
        });

        it('opens the menu and shows correct options', () => {
            cy.contains('li', 'pending text').find('button[aria-label="change redaction type and accept"]').click();

            cy.get('[role="menu"]').should('be.visible');

            cy.contains('[role="menuitem"]', 'Accept as Operational Data').should('be.visible');
            cy.contains('[role="menuitem"]', 'Accept as Data Subject Information').should('be.visible');
            cy.contains('[role="menuitem"]', 'Accept as Third-Party PII').should('not.exist');
        });

        it('calls onChangeTypeAndAccept when a new type is selected', () => {
            cy.contains('li', 'pending text').find('button[aria-label="change redaction type and accept"]').click();
            cy.contains('[role="menuitem"]', 'Accept as Operational Data').click();

            cy.get('@onChangeTypeAndAccept').should('have.been.calledOnceWith', 'p1', 'OP_DATA');

            cy.get('[role="menu"]').should('not.exist');
        });
    });

    context('Scroll to Item', () => {
        beforeEach(() => {
            cy.clock();
        });

        it('expands the correct accordion and scrolls to the item', () => {
            const scrollIntoViewStub = cy.stub().as('scrollIntoView');
            cy.fullMount(
                <RedactionSidebar {...baseProps} redactions={mockRedactions} scrollToId="a1" />,
                mountOpts
            ).then(({ component, rerender }) => {
                cy.contains('li', 'accepted text').then($el => {
                    $el[0].scrollIntoView = scrollIntoViewStub;
                });
            });

            cy.contains('accepted (2)').parents('.MuiAccordion-root').should('be.have.class', 'Mui-expanded');

            cy.tick(150);

            cy.get('@scrollIntoView').should('have.been.calledOnce');

            cy.contains('li', 'accepted text').should('have.css', 'background-color', 'rgba(255, 214, 10, 0.4)');

            cy.tick(2000);

            cy.contains('li', 'accepted text').should('not.have.css', 'background-color', 'rgba(255, 214, 10, 0.4)');

            cy.get('@removeScrollId').should('have.been.calledOnce');
        });
    });

    context('Context Management', () => {
        beforeEach(() => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} />, mountOpts);
            // Set a larger viewport to prevent clipping issues in headless mode
            cy.viewport(1280, 720);
            cy.contains('accepted (2)').click();
        });

        it('shows context button for accepted/manual items and displays existing context', () => {
            cy.contains('li', '"accepted text"').scrollIntoView().within(() => {
                cy.get('[data-testid="AddIcon"]')
                  .parents('button')
                  .should('be.visible')
                  .and('contain', 'Context');
            });

            cy.contains('li', '"accepted with context"').scrollIntoView().within(() => {
                cy.get('[data-testid="EditIcon"]')
                    .parents('button')
                    .should('be.visible')
                    .and('contain', 'Context');
            });

            cy.contains('li', '"accepted with context"').scrollIntoView().within(() => {
                cy.get('[data-testid="EditIcon"]')
                    .parents('button')
                    .parent()
                    .should('be.visible')
                    .and('contain', 'This is existing contex...');
            });
        });

        it('opens and closes the context manager', () => {
            cy.contains('li', '"accepted text"').as('redactionItem');

            cy.get('@redactionItem').within(() => {
                cy.contains('button', 'Context').click();
                cy.get('textarea[name="Context for Disclosure"]').should('be.visible');

                cy.contains('button', 'Cancel').click();
                cy.get('textarea[name="Context for Disclosure"]').should('not.exist');
            });
        });
    });
});