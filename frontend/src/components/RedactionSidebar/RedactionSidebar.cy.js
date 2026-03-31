import React from 'react';
import { RedactionSidebar } from './RedactionSidebar';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

describe('<RedactionSidebar />', () => {
    // Individual (non-merged, non-group) display items in new format
    const mockRedactions = {
        pending: {
            total: 1,
            items: [
                { id: 'p1', ids: ['p1'], isMerged: false, isGroup: false, text: 'pending text', redaction_type: 'PII', is_suggestion: true },
            ],
        },
        accepted: {
            total: 2,
            items: [
                { id: 'a1', ids: ['a1'], isMerged: false, isGroup: false, text: 'accepted text', redaction_type: 'OP_DATA', is_suggestion: false, context: null },
                { id: 'a2', ids: ['a2'], isMerged: false, isGroup: false, text: 'accepted with context', redaction_type: 'DS_INFO', is_suggestion: false, context: { text: 'This is existing context.' } },
            ],
        },
        rejected: {
            total: 1,
            items: [
                { id: 'r1', ids: ['r1'], isMerged: false, isGroup: false, text: 'rejected text', redaction_type: 'PII', is_suggestion: true, justification: 'Not relevant' },
            ],
        },
        manual: {
            total: 1,
            items: [
                { id: 'm1', ids: ['m1'], isMerged: false, isGroup: false, text: 'manual text', redaction_type: 'DS_INFO', is_suggestion: false },
            ],
        },
    };

    const mockExemptionTemplates = [
        { id: 1, name: 'S.40 - Personal Information', description: '' },
        { id: 2, name: 'S.42 - Legal Privilege', description: '' },
    ];

    let baseProps;

    beforeEach(() => {
        baseProps = {
            onAccept: cy.stub().as('onAccept'),
            onReject: cy.stub().as('onReject'),
            onRemove: cy.stub().as('onRemove'),
            onChangeTypeAndAccept: cy.stub().as('onChangeTypeAndAccept'),
            onBulkAccept: cy.stub().as('onBulkAccept'),
            onBulkReject: cy.stub().as('onBulkReject'),
            onRejectAsDisclosable: cy.stub().as('onRejectAsDisclosable'),
            onSplitMerge: cy.stub().as('onSplitMerge'),
            onSuggestionMouseEnter: cy.stub().as('onSuggestionMouseEnter'),
            onSuggestionMouseLeave: cy.stub().as('onSuggestionMouseLeave'),
            scrollToId: null,
            removeScrollId: cy.stub().as('removeScrollId'),
            onContextSave: cy.stub().as('onContextSave'),
            onCardClick: cy.stub().as('onCardClick'),
            exemptionTemplates: mockExemptionTemplates,
        };
    });

    it('renders empty state when no redactions are provided', () => {
        const emptyRedactions = {
            pending: { total: 0, items: [] },
            accepted: { total: 0, items: [] },
            rejected: { total: 0, items: [] },
            manual: { total: 0, items: [] },
        };
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
            cy.contains('li', '"accepted text"').contains('button', 'Remove').should('exist');
        });

        it('renders correct buttons for the "rejected" section', () => {
            cy.contains('rejected (1)').click();
            cy.contains('li', 'rejected text').contains('button', 'Re-evaluate').should('exist');
        });

        it('renders correct buttons for the "manual" section', () => {
            cy.contains('manual (1)').click();
            cy.contains('li', 'manual text').contains('button', 'Remove').should('exist');
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
            cy.get('@onReject').should('have.been.calledOnceWith', mockRedactions.pending.items[0]);
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

        it('shows exemption templates in the reject dropdown', () => {
            cy.contains('li', 'pending text').find('button[aria-label="reject with reason"]').click();
            cy.contains('[role="menuitem"]', 'S.40 - Personal Information').should('be.visible');
            cy.contains('[role="menuitem"]', 'S.42 - Legal Privilege').should('be.visible');
        });

        it('calls onRejectAsDisclosable with template name when a template is selected', () => {
            cy.contains('li', 'pending text').find('button[aria-label="reject with reason"]').click();
            cy.contains('[role="menuitem"]', 'S.40 - Personal Information').click();
            cy.get('@onRejectAsDisclosable').should('have.been.calledOnceWith', ['p1'], 'S.40 - Personal Information');
        });

        it('filters templates by search input', () => {
            cy.contains('li', 'pending text').find('button[aria-label="reject with reason"]').click();
            cy.get('input[placeholder="Search exemptions..."]').type('Legal');
            cy.contains('[role="menuitem"]', 'S.42 - Legal Privilege').should('be.visible');
            cy.contains('[role="menuitem"]', 'S.40 - Personal Information').should('not.exist');
        });

        it('shows "No exemptions found" when search matches nothing', () => {
            cy.contains('li', 'pending text').find('button[aria-label="reject with reason"]').click();
            cy.get('input[placeholder="Search exemptions..."]').type('zzz');
            cy.contains('[role="menuitem"]', 'No exemptions found').should('be.visible');
        });

        it('shows "No exemptions found" when no templates are configured', () => {
            cy.fullMount(
                <RedactionSidebar {...baseProps} redactions={mockRedactions} exemptionTemplates={[]} />,
                mountOpts
            );
            cy.contains('li', 'pending text').find('button[aria-label="reject with reason"]').click();
            cy.contains('[role="menuitem"]', 'No exemptions found').should('be.visible');
        });

        it('calls onCardClick with the item id when card content is clicked', () => {
            cy.contains('li', 'pending text').contains('"pending text"').click();
            cy.get('@onCardClick').should('have.been.calledOnceWith', 'p1');
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
                  .should('exist')
                  .and('contain', 'Context');
            });

            cy.contains('li', '"accepted with context"').scrollIntoView().within(() => {
                cy.get('[data-testid="EditIcon"]')
                    .parents('button')
                    .should('exist')
                    .and('contain', 'Context');
            });

            cy.contains('li', '"accepted with context"').scrollIntoView().within(() => {
                cy.get('[data-testid="EditIcon"]')
                    .parents('button')
                    .parent()
                    .should('exist')
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

    context('Grouped items', () => {
        const mockRedactionsWithGroup = {
            pending: {
                total: 3,
                items: [
                    {
                        key: 'john doe::pii',
                        isGroup: true,
                        text: 'John Doe',
                        redaction_type: 'PII',
                        items: [
                            { id: 'g1', ids: ['g1'], isMerged: false, isGroup: false, text: 'John Doe', redaction_type: 'PII', is_suggestion: true },
                            { id: 'g2', ids: ['g2'], isMerged: false, isGroup: false, text: 'John Doe', redaction_type: 'PII', is_suggestion: true },
                            { id: 'g3', ids: ['g3'], isMerged: false, isGroup: false, text: 'John Doe', redaction_type: 'PII', is_suggestion: true },
                        ],
                    },
                ],
            },
            accepted: { total: 0, items: [] },
            rejected: { total: 0, items: [] },
            manual: { total: 0, items: [] },
        };

        beforeEach(() => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactionsWithGroup} />, mountOpts);
        });

        it('shows section count as total DB records', () => {
            cy.contains('pending (3)').should('be.visible');
        });

        it('renders group header with text, type, and occurrence count', () => {
            cy.contains('"John Doe"').should('be.visible');
            cy.contains('Third-Party PII · 3 occurrences').should('be.visible');
        });

        it('renders Accept All and Reject All buttons on pending group header', () => {
            cy.contains('button', 'Accept All').should('be.visible');
            cy.contains('button', 'Reject All').should('be.visible');
        });

        it('calls onBulkAccept with all group IDs when Accept All is clicked', () => {
            cy.contains('button', 'Accept All').click();
            cy.get('@onBulkAccept').should('have.been.calledOnceWith', ['g1', 'g2', 'g3']);
        });

        it('calls onBulkReject with all group IDs when Reject All is clicked', () => {
            cy.contains('button', 'Reject All').click();
            cy.get('@onBulkReject').should('have.been.calledOnceWith', ['g1', 'g2', 'g3']);
        });

        it('shows exemption templates in group header dropdown and calls onRejectAsDisclosable', () => {
            cy.get('button[aria-label="reject all with reason"]').click();
            cy.contains('[role="menuitem"]', 'S.40 - Personal Information').should('be.visible').click();
            cy.get('@onRejectAsDisclosable').should('have.been.calledOnceWith', ['g1', 'g2', 'g3'], 'S.40 - Personal Information');
        });

        it('expands group to show individual items when expand icon is clicked', () => {
            cy.contains('button', 'Accept All').should('be.visible');
            // Individual items hidden initially
            cy.contains('li', 'g1').should('not.exist');

            cy.get('button[aria-label="expand group"]').click();

            // Individual items visible after expanding
            cy.contains('"John Doe"').should('be.visible');
        });

        it('collapses group when collapse icon is clicked', () => {
            cy.get('button[aria-label="expand group"]').click();
            cy.get('button[aria-label="collapse group"]').should('be.visible').click();
            cy.get('button[aria-label="expand group"]').should('be.visible');
        });

        it('calls onCardClick with first group id when group card content is clicked', () => {
            cy.contains('"John Doe"').click();
            cy.get('@onCardClick').should('have.been.calledOnceWith', 'g1');
        });

        it('does not call onCardClick when the expand/collapse icon is clicked', () => {
            cy.get('button[aria-label="expand group"]').click();
            cy.get('@onCardClick').should('not.have.been.called');
        });
    });

    context('Merged items', () => {
        const mockRedactionsWithMerged = {
            pending: {
                total: 2,
                items: [
                    {
                        id: 'merge1',
                        ids: ['merge1', 'merge2'],
                        isMerged: true,
                        isGroup: false,
                        text: 'John Doe',
                        redaction_type: 'PII',
                        is_suggestion: true,
                    },
                ],
            },
            accepted: { total: 0, items: [] },
            rejected: { total: 0, items: [] },
            manual: { total: 0, items: [] },
        };

        beforeEach(() => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactionsWithMerged} />, mountOpts);
        });

        it('shows section count as total DB records', () => {
            cy.contains('pending (2)').should('be.visible');
        });

        it('renders the merged badge', () => {
            cy.contains('merged (2)').should('be.visible');
        });

        it('renders a split button for merged items', () => {
            cy.get('button[aria-label="split merged redaction"]').should('be.visible');
        });

        it('calls onSplitMerge with the merge key when Split is clicked', () => {
            cy.get('button[aria-label="split merged redaction"]').click();
            cy.get('@onSplitMerge').should('have.been.calledOnceWith', 'merge1:merge2');
        });

        it('calls onBulkAccept with all merged IDs when Accept is clicked', () => {
            cy.contains('button', 'Accept').click();
            cy.get('@onBulkAccept').should('have.been.calledOnceWith', ['merge1', 'merge2']);
        });

        it('calls onBulkReject with all merged IDs when Reject is clicked', () => {
            cy.contains('button', 'Reject').click();
            cy.get('@onBulkReject').should('have.been.calledOnceWith', ['merge1', 'merge2']);
        });

        it('shows exemption templates in merged item dropdown and calls onRejectAsDisclosable', () => {
            cy.get('button[aria-label="reject with reason"]').click();
            cy.contains('[role="menuitem"]', 'S.40 - Personal Information').should('be.visible').click();
            cy.get('@onRejectAsDisclosable').should('have.been.calledOnceWith', ['merge1', 'merge2'], 'S.40 - Personal Information');
        });

        it('does not show the change-type dropdown for merged items', () => {
            cy.get('button[aria-label="change redaction type and accept"]').should('not.exist');
        });
    });

    context('REMOVE Highlight Tool button', () => {
        it('renders the Remove button when documentCompleted is false', () => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} activeHighlightType={null} onToggleHighlightTool={cy.stub()} documentCompleted={false} />, mountOpts);
            cy.contains('button', 'Remove').should('be.visible');
        });

        it('does not render the Remove button when documentCompleted is true', () => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} activeHighlightType={null} onToggleHighlightTool={cy.stub()} documentCompleted={true} />, mountOpts);
            cy.contains('button', 'Remove').should('not.exist');
        });

        it('calls onToggleHighlightTool with REMOVE when the Remove button is clicked', () => {
            const onToggleHighlightTool = cy.stub().as('onToggleHighlightTool');
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} activeHighlightType={null} onToggleHighlightTool={onToggleHighlightTool} documentCompleted={false} />, mountOpts);
            cy.contains('button', 'Remove').click();
            cy.get('@onToggleHighlightTool').should('have.been.calledOnceWith', 'REMOVE');
        });

        it('shows the Remove button as active when activeHighlightType is REMOVE', () => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} activeHighlightType="REMOVE" onToggleHighlightTool={cy.stub()} documentCompleted={false} />, mountOpts);
            cy.contains('button', 'Remove').should('have.css', 'opacity', '1');
        });

        it('shows the Remove button as inactive when a different tool is active', () => {
            cy.fullMount(<RedactionSidebar {...baseProps} redactions={mockRedactions} activeHighlightType="PII" onToggleHighlightTool={cy.stub()} documentCompleted={false} />, mountOpts);
            cy.contains('button', 'Remove').should('have.css', 'opacity', '0.45');
        });
    });
});
