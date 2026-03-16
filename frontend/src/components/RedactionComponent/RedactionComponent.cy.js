import React from 'react';
import { PathnameContext } from 'next/dist/shared/lib/hooks-client-context.shared-runtime';
import { RedactionComponent } from './RedactionComponent';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

const mockDocument = {
    id: 'doc-1',
    case: 'case-1',
    filename: 'test-document.pdf',
    extracted_text: 'This is a test document with some sensitive information like John Doe and email@example.com that should be redacted.',
    status: 'Ready for Review',
};

const mockRedactions = [
    {
        id: 'r1',
        text: 'John Doe',
        redaction_type: 'PII',
        is_suggestion: true,
        is_accepted: false,
        justification: null,
        start_char: 61,
        end_char: 68,
    },
    {
        id: 'r2',
        text: 'email@example.com',
        redaction_type: 'PII',
        is_suggestion: true,
        is_accepted: true,
        justification: null,
        start_char: 74,
        end_char: 90,
    },
    {
        id: 'r3',
        text: 'sensitive information',
        redaction_type: 'OP_DATA',
        is_suggestion: true,
        is_accepted: false,
        justification: 'Not actually sensitive',
        start_char: 34,
        end_char: 54,
    },
    {
        id: 'r4',
        text: 'test document',
        redaction_type: 'DS_INFO',
        is_suggestion: false,
        is_accepted: true,
        justification: null,
        start_char: 10,
        end_char: 22,
    },
];

// Adjacent same-type items that will be merged (gap = 1 char, same type)
const mockRedactionsWithAdjacent = [
    {
        id: 'adj1',
        text: 'John',
        redaction_type: 'PII',
        is_suggestion: true,
        is_accepted: false,
        justification: null,
        start_char: 62,
        end_char: 66,
    },
    {
        id: 'adj2',
        text: 'Doe',
        redaction_type: 'PII',
        is_suggestion: true,
        is_accepted: false,
        justification: null,
        start_char: 67,
        end_char: 70,
    },
];

// Same text+type at different positions — will be grouped
const mockRedactionsWithDuplicates = [
    {
        id: 'dup1',
        text: 'information',
        redaction_type: 'OP_DATA',
        is_suggestion: true,
        is_accepted: false,
        justification: null,
        start_char: 25,
        end_char: 36,
    },
    {
        id: 'dup2',
        text: 'information',
        redaction_type: 'OP_DATA',
        is_suggestion: true,
        is_accepted: false,
        justification: null,
        start_char: 60,
        end_char: 71,
    },
];

const mountRedactionComponent = (document = mockDocument, redactions = mockRedactions) => {
    return cy.fullMount(
        <PathnameContext.Provider value="/cases/case-1/document/doc-1/review">
            <RedactionComponent document={document} initialRedactions={redactions} />
        </PathnameContext.Provider>,
        mountOpts
    );
};

describe('<RedactionComponent />', () => {
    beforeEach(() => {
        cy.intercept('PATCH', '**/cases/document/redaction/*', (req) => {
            const id = req.url.split('/').pop();
            const existing = mockRedactions.find(r => r.id === id) || {};
            req.reply({ statusCode: 200, body: { ...existing, ...req.body, id } });
        }).as('updateRedaction');
        cy.intercept('DELETE', '**/cases/document/redaction/*', { statusCode: 204 }).as('deleteRedaction');
        cy.intercept('POST', '**/cases/document/*/redaction', (req) => {
            req.reply({ statusCode: 201, body: { ...req.body, id: 'new-redaction-id' } });
        }).as('createRedaction');
        cy.intercept('PATCH', '**/cases/documents/*', { statusCode: 200, body: { ...mockDocument, status: 'Completed' } }).as('markComplete');
        cy.intercept('PATCH', '**/cases/document/*/redactions/bulk/', (req) => {
            const updated = req.body.ids.map(id => ({
                id,
                is_accepted: req.body.is_accepted,
                justification: req.body.justification,
                is_suggestion: true,
                text: 'bulk item',
                redaction_type: 'PII',
                start_char: 0,
                end_char: 3,
            }));
            req.reply({ statusCode: 200, body: updated });
        }).as('bulkUpdateRedaction');
    });

    context('Initial Render', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('renders the document filename in the header', () => {
            cy.contains('h1', 'test-document.pdf').should('be.visible');
        });

        it('renders the "Back to Case" button with correct link', () => {
            cy.contains('a', 'Back to Case')
                .should('be.visible')
                .and('have.attr', 'href', '/cases/case-1');
        });

        it('renders the RedactionSidebar with correct counts', () => {
            cy.contains('pending (1)').should('be.visible');
            cy.contains('accepted (1)').should('be.visible');
            cy.contains('rejected (1)').should('be.visible');
            cy.contains('manual (1)').should('be.visible');
        });

        it('renders the document text in the viewer', () => {
            cy.contains('This is a test document').should('be.visible');
        });
    });

    context('Mark as Complete Button', () => {
        it('disables button when there are pending suggestions', () => {
            mountRedactionComponent();

            cy.contains('button', 'Mark as Complete').should('be.disabled');
        });

        it('shows tooltip explaining why button is disabled', () => {
            mountRedactionComponent();

            cy.contains('button', 'Mark as Complete').trigger('mouseover', { force: true });
            cy.contains('You must resolve all AI suggestions before completing.').should('be.visible');
        });

        it('enables button when no pending suggestions exist', () => {
            const noPendingRedactions = mockRedactions.filter(r => r.id !== 'r1');
            mountRedactionComponent(mockDocument, noPendingRedactions);

            cy.contains('button', 'Mark as Complete').should('not.be.disabled');
        });

        it('calls markAsComplete API and shows success toast', () => {
            const noPendingRedactions = mockRedactions.filter(r => r.id !== 'r1');
            mountRedactionComponent(mockDocument, noPendingRedactions);

            cy.contains('button', 'Mark as Complete').click();

            cy.wait('@markComplete');
            cy.contains('Document is ready for disclosure.').should('be.visible');
        });

        it('shows "Ready for Disclosure" button when document is completed', () => {
            const completedDocument = { ...mockDocument, status: 'Completed' };
            mountRedactionComponent(completedDocument, []);

            cy.contains('button', 'Ready for Disclosure').should('be.visible');
            cy.contains('button', 'Mark as Complete').should('not.exist');
        });
    });

    context('Accept Suggestion', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('calls updateRedaction API when accepting a suggestion', () => {
            cy.contains('pending (1)').click();
            cy.contains('li', 'John Doe').contains('button', 'Accept').click();

            cy.wait('@updateRedaction').its('request.body').should('deep.include', { is_accepted: true });
        });

        it('moves suggestion to accepted list after accepting', () => {
            cy.intercept('PATCH', '**/cases/document/redaction/r1', {
                statusCode: 200,
                body: { ...mockRedactions[0], is_accepted: true },
            }).as('acceptRedaction');

            cy.contains('pending (1)').click();
            cy.contains('li', 'John Doe').contains('button', 'Accept').click();

            cy.wait('@acceptRedaction');
            cy.contains('pending').should('not.exist');
            cy.contains('accepted (2)').should('be.visible');
        });
    });

    context('Reject Suggestion', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('opens rejection dialog when clicking Reject', () => {
            cy.contains('pending (1)').click();
            cy.contains('li', 'John Doe').contains('button', 'Reject').click();

            cy.get('[role="dialog"]').should('be.visible');
            cy.contains('Rejection Reason').should('be.visible');
        });

        it('calls updateRedaction API with justification when rejecting', () => {
            cy.contains('li', 'John Doe').contains('button', 'Reject').click();

            cy.get('[role="dialog"]').within(() => {
                cy.get('textarea#reject-reason').type('This is not PII');
                cy.contains('button', 'Submit').click();
            });

            cy.wait('@updateRedaction').its('request.body').should('deep.include', {
                is_accepted: false,
                justification: 'This is not PII',
            });
        });
    });

    context('Remove Redaction', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('calls deleteRedaction API for manual redactions', () => {
            cy.contains('manual (1)').click();
            cy.contains('li', 'test document').contains('button', 'Remove').click();

            cy.wait('@deleteRedaction');
            cy.contains('Redaction deleted.').should('be.visible');
        });

        it('reverts accepted suggestion to pending when removed', () => {
            cy.intercept('PATCH', '**/cases/document/redaction/r2', {
                statusCode: 200,
                body: { ...mockRedactions[1], is_accepted: false, justification: null },
            }).as('revertRedaction');

            cy.contains('accepted (1)').click();
            cy.contains('li', 'email@example.com').contains('button', 'Remove').click();

            cy.wait('@revertRedaction');
            cy.contains('Suggestion reverted to pending.').should('be.visible');
        });
    });

    context('Change Type and Accept', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('opens menu with alternative redaction types', () => {
            cy.contains('li', 'John Doe').find('button[aria-label="change redaction type and accept"]').click();

            cy.get('[role="menu"]').should('be.visible');
            cy.contains('[role="menuitem"]', 'Accept as Operational Data').should('be.visible');
            cy.contains('[role="menuitem"]', 'Accept as Data Subject Information').should('be.visible');
        });

        it('calls updateRedaction API with new type when selected', () => {
            cy.contains('li', 'John Doe').find('button[aria-label="change redaction type and accept"]').click();
            cy.contains('[role="menuitem"]', 'Accept as Operational Data').click();

            cy.wait('@updateRedaction').its('request.body').should('deep.include', {
                redaction_type: 'OP_DATA',
                is_accepted: true,
                is_suggestion: false,
            });
        });
    });

    context('Re-evaluate Rejected Suggestion', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('reverts rejected suggestion to pending when Re-evaluate is clicked', () => {
            cy.intercept('PATCH', '**/cases/document/redaction/r3', {
                statusCode: 200,
                body: { ...mockRedactions[2], is_accepted: false, justification: null },
            }).as('revertRejected');

            cy.contains('rejected (1)').click();
            cy.contains('li', 'sensitive information').contains('button', 'Re-evaluate').click();

            cy.wait('@revertRejected');
            cy.contains('Suggestion reverted to pending.').should('be.visible');
        });
    });

    context('Adjacent Span Merging', () => {
        beforeEach(() => {
            mountRedactionComponent(mockDocument, mockRedactionsWithAdjacent);
        });

        it('merges adjacent same-type spans into a single display item', () => {
            // Two raw items become one merged display item
            cy.contains('pending (2)').should('be.visible');
            cy.contains('"John Doe"').should('be.visible');
            cy.contains('merged (2)').should('be.visible');
        });

        it('shows a split button on merged items', () => {
            cy.get('button[aria-label="split merged redaction"]').should('be.visible');
        });

        it('splits merged item into individual items when Split is clicked', () => {
            cy.get('button[aria-label="split merged redaction"]').click();

            // After split, two individual items appear
            cy.contains('"John"').should('be.visible');
            cy.contains('"Doe"').should('be.visible');
            cy.contains('merged (2)').should('not.exist');
        });

        it('calls bulk API when Accept is clicked on a merged item', () => {
            cy.contains('button', 'Accept').click();

            cy.wait('@bulkUpdateRedaction').its('request.body').should('deep.include', {
                is_accepted: true,
                ids: ['adj1', 'adj2'],
            });
        });

        it('calls bulk API when Reject is clicked on a merged item', () => {
            cy.contains('button', 'Reject').click();

            cy.get('[role="dialog"]').within(() => {
                cy.get('textarea#reject-reason').type('Not relevant');
                cy.contains('button', 'Submit').click();
            });

            cy.wait('@bulkUpdateRedaction').its('request.body').should('deep.include', {
                is_accepted: false,
                justification: 'Not relevant',
            });
        });
    });

    context('Same-Text Grouping', () => {
        beforeEach(() => {
            mountRedactionComponent(mockDocument, mockRedactionsWithDuplicates);
        });

        it('groups same-text same-type items under a group header', () => {
            cy.contains('pending (2)').should('be.visible');
            cy.contains('Third-Party PII · 2 occurrences').should('not.exist');
            cy.contains('Operational Data · 2 occurrences').should('be.visible');
        });

        it('shows Accept All and Reject All on group headers', () => {
            cy.contains('button', 'Accept All').should('be.visible');
            cy.contains('button', 'Reject All').should('be.visible');
        });

        it('calls bulk API when Accept All is clicked', () => {
            cy.contains('button', 'Accept All').click();

            cy.wait('@bulkUpdateRedaction').then((interception) => {
                expect(interception.request.body).to.deep.include({ is_accepted: true });
                expect(interception.request.body.ids).to.include.members(['dup1', 'dup2']);
            });
        });

        it('calls bulk API with justification when Reject All is submitted', () => {
            cy.contains('button', 'Reject All').click();

            cy.get('[role="dialog"]').within(() => {
                cy.get('textarea#reject-reason').type('Not relevant group');
                cy.contains('button', 'Submit').click();
            });

            cy.wait('@bulkUpdateRedaction').its('request.body').should('deep.include', {
                is_accepted: false,
                justification: 'Not relevant group',
            });
        });

        it('expands group to show individual items', () => {
            cy.get('button[aria-label="expand group"]').click();
            // Individual items visible after expanding
            cy.contains('"information"').should('be.visible');
        });
    });

    context('Resubmit Document', () => {
        beforeEach(() => {
            cy.intercept('POST', '**/cases/documents/doc-1/resubmit', { statusCode: 200 }).as('resubmitDocument');
        });

        it('shows resubmit icon when document is not completed', () => {
            mountRedactionComponent();

            cy.get('button[aria-label="Resubmit for processing"]').should('be.visible');
        });

        it('hides resubmit icon when document is completed', () => {
            const completedDocument = { ...mockDocument, status: 'Completed' };
            mountRedactionComponent(completedDocument, []);

            cy.get('button[aria-label="Resubmit for processing"]').should('not.exist');
        });

        it('opens confirmation dialog when resubmit icon is clicked', () => {
            mountRedactionComponent();

            cy.get('button[aria-label="Resubmit for processing"]').click();

            cy.get('[role="dialog"]').should('be.visible');
            cy.contains('Resubmit Document').should('be.visible');
            cy.contains('This will delete all current redactions').should('be.visible');
        });

        it('closes dialog when cancel is clicked', () => {
            mountRedactionComponent();

            cy.get('button[aria-label="Resubmit for processing"]').click();
            cy.get('[role="dialog"]').should('be.visible');

            cy.get('[role="dialog"]').contains('button', 'Cancel').click();

            cy.get('[role="dialog"]').should('not.exist');
        });

        it('calls resubmit API and shows success toast', () => {
            mountRedactionComponent();

            cy.get('button[aria-label="Resubmit for processing"]').click();
            cy.get('[role="dialog"]').contains('button', 'Resubmit').click();

            cy.wait('@resubmitDocument');
            cy.contains('Document resubmitted for processing.').should('be.visible');
        });

        it('shows error toast when resubmit fails', () => {
            cy.intercept('POST', '**/cases/documents/doc-1/resubmit', { statusCode: 500 }).as('failedResubmit');
            mountRedactionComponent();

            cy.get('button[aria-label="Resubmit for processing"]').click();
            cy.get('[role="dialog"]').contains('button', 'Resubmit').click();

            cy.wait('@failedResubmit');
            cy.contains('Failed to resubmit document. Please try again.').should('be.visible');
        });
    });

    context('Font Size Controls', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('renders font size increase and decrease buttons', () => {
            cy.get('button[aria-label="Decrease font size"]').should('be.visible');
            cy.get('button[aria-label="Increase font size"]').should('be.visible');
        });

        it('increases font size when A+ is clicked', () => {
            cy.get('.MuiPaper-root').should('have.css', 'font-size', '16px');

            cy.get('button[aria-label="Increase font size"]').click();

            cy.get('.MuiPaper-root').should('have.css', 'font-size').and('not.eq', '16px');
        });

        it('decreases font size when A- is clicked', () => {
            cy.get('.MuiPaper-root').should('have.css', 'font-size', '16px');

            cy.get('button[aria-label="Decrease font size"]').click();

            cy.get('.MuiPaper-root').should('have.css', 'font-size').and('not.eq', '16px');
        });

        it('disables decrease button at minimum font size', () => {
            // Click decrease until minimum
            cy.get('button[aria-label="Decrease font size"]').click();
            cy.get('button[aria-label="Decrease font size"]').click();

            cy.get('button[aria-label="Decrease font size"]').should('be.disabled');
        });

        it('disables increase button at maximum font size', () => {
            // Click increase until maximum
            cy.get('button[aria-label="Increase font size"]').click();
            cy.get('button[aria-label="Increase font size"]').click();
            cy.get('button[aria-label="Increase font size"]').click();

            cy.get('button[aria-label="Increase font size"]').should('be.disabled');
        });
    });

    context('Sidebar Resize Handle', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('renders the resize handle', () => {
            cy.get('[data-testid="resize-handle"]').should('be.visible');
        });

        it('changes sidebar width when dragging the resize handle', () => {
            cy.get('[data-testid="resize-handle"]').then(($handle) => {
                const handle = $handle[0];
                const handleRect = handle.getBoundingClientRect();
                const startX = handleRect.left + handleRect.width / 2;
                const startY = handleRect.top + handleRect.height / 2;
                const doc = handle.ownerDocument;

                // Trigger mousedown on the handle element
                handle.dispatchEvent(new MouseEvent('mousedown', { clientX: startX, clientY: startY, bubbles: true }));

                // Trigger mousemove on the document to simulate dragging left (widening sidebar)
                doc.dispatchEvent(new MouseEvent('mousemove', { clientX: startX - 100, clientY: startY, bubbles: true }));
                doc.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
            });

            // Sidebar wrapper should have a different width than the default 450px
            cy.get('[data-testid="resize-handle"]').next().invoke('outerWidth').should('not.eq', 450);
        });
    });

    context('Disclosable Quick-Reject', () => {
        it('calls updateRedaction with Disclosable justification for a single item', () => {
            cy.intercept('PATCH', '**/cases/document/redaction/r1', (req) => {
                req.reply({ statusCode: 200, body: { ...mockRedactions[0], is_accepted: false, justification: req.body.justification } });
            }).as('disclosableUpdate');

            mountRedactionComponent();

            cy.contains('li', 'John Doe').find('button[aria-label="reject with reason"]').click();
            cy.contains('[role="menuitem"]', 'Reject as Disclosable').click();

            cy.wait('@disclosableUpdate').its('request.body').should('deep.include', {
                is_accepted: false,
                justification: 'Disclosable',
            });
        });

        it('calls bulk API with Disclosable justification for merged items', () => {
            mountRedactionComponent(mockDocument, mockRedactionsWithAdjacent);

            cy.get('button[aria-label="reject with reason"]').click();
            cy.contains('[role="menuitem"]', 'Reject as Disclosable').click();

            cy.wait('@bulkUpdateRedaction').its('request.body').should('deep.include', {
                is_accepted: false,
                justification: 'Disclosable',
                ids: ['adj1', 'adj2'],
            });
        });

        it('shows error toast when disclosable reject fails', () => {
            cy.intercept('PATCH', '**/cases/document/redaction/r1', { statusCode: 500 }).as('failedDisclosable');
            mountRedactionComponent();

            cy.contains('li', 'John Doe').find('button[aria-label="reject with reason"]').click();
            cy.contains('[role="menuitem"]', 'Reject as Disclosable').click();

            cy.wait('@failedDisclosable');
            cy.contains('Failed to mark as disclosable. Please try again.').should('be.visible');
        });
    });

    context('Manual Redaction Overlap Handling', () => {
        beforeEach(() => {
            mountRedactionComponent();
        });

        it('does not create a duplicate when selecting text already redacted with the same type', () => {
            // r4: DS_INFO, accepted, chars 10–22 — first highlighted span in the viewer
            cy.get('[data-testid="document-viewer"] span').first().then($span => {
                const textNode = $span[0].firstChild;
                const range = document.createRange();
                range.setStart(textNode, 0);
                range.setEnd(textNode, 4);
                window.getSelection().removeAllRanges();
                window.getSelection().addRange(range);
            });
            cy.get('[data-testid="document-viewer"]').trigger('mouseup');

            // Popover opens — select DS_INFO (same type as r4)
            cy.get('[role="presentation"]').should('be.visible');
            cy.get('[role="combobox"]').click();
            cy.get('[role="listbox"]').contains('li', 'Data Subject Information').click();
            cy.contains('button', 'Redact').click();

            cy.contains('This text is already redacted with this classification.').should('be.visible');
            cy.get('@createRedaction.all').should('have.length', 0);
        });

        it('updates the existing redaction type when selecting already-redacted text with a different type', () => {
            // r4: DS_INFO, accepted, chars 10–22 — first highlighted span in the viewer
            cy.get('[data-testid="document-viewer"] span').first().then($span => {
                const textNode = $span[0].firstChild;
                const range = document.createRange();
                range.setStart(textNode, 0);
                range.setEnd(textNode, 4);
                window.getSelection().removeAllRanges();
                window.getSelection().addRange(range);
            });
            cy.get('[data-testid="document-viewer"]').trigger('mouseup');

            // Popover opens — default type is PII (different from r4's DS_INFO)
            cy.get('[role="presentation"]').should('be.visible');
            cy.contains('button', 'Redact').click();

            cy.wait('@updateRedaction').its('request.body').should('deep.include', {
                redaction_type: 'PII',
                is_accepted: true,
                is_suggestion: false,
            });
            cy.contains('Redaction classification updated.').should('be.visible');
            cy.get('@createRedaction.all').should('have.length', 0);
        });

        it('creates a new redaction for a selection with no overlap', () => {
            // "This" (chars 0–4) — not covered by any existing redaction
            cy.get('[data-testid="document-viewer"]').then($paper => {
                const textNode = $paper[0].firstChild;
                const range = document.createRange();
                range.setStart(textNode, 0);
                range.setEnd(textNode, 4);
                window.getSelection().removeAllRanges();
                window.getSelection().addRange(range);
            });
            cy.get('[data-testid="document-viewer"]').trigger('mouseup');

            cy.get('[role="presentation"]').should('be.visible');
            cy.contains('button', 'Redact').click();

            cy.wait('@createRedaction');
            cy.contains('Redaction created successfully.').should('be.visible');
        });
    });

    context('Error Handling', () => {
        it('shows error toast when accept fails', () => {
            cy.intercept('PATCH', '**/cases/document/redaction/r1', { statusCode: 500 }).as('failedUpdate');
            mountRedactionComponent();

            cy.contains('li', 'John Doe').should('be.visible');
            cy.contains('li', 'John Doe').contains('button', 'Accept').should('be.visible').click();

            cy.wait('@failedUpdate');

            cy.contains('Failed to accept suggestion. Please try again.').should('be.visible');
        });

        it('shows error toast when delete fails', () => {
            cy.intercept('DELETE', '**/cases/document/redaction/r4', { statusCode: 500 }).as('failedDelete');
            mountRedactionComponent();

            cy.contains('manual (1)').click();
            cy.contains('li', 'test document').should('be.visible');
            cy.contains('li', 'test document').contains('button', 'Remove').should('be.visible').click();

            cy.wait('@failedDelete');
            cy.contains('Failed to delete redaction. Please try again.').should('be.visible');
        });

        it('shows error toast when mark as complete fails', () => {
            cy.intercept('PATCH', '**/cases/documents/doc-1', { statusCode: 500 }).as('failedComplete');
            const noPendingRedactions = mockRedactions.filter(r => r.id !== 'r1');
            mountRedactionComponent(mockDocument, noPendingRedactions);

            cy.contains('button', 'Mark as Complete').should('be.visible').click();

            cy.wait('@failedComplete');
            cy.contains('Failed to mark document as complete. Please try again.').should('be.visible');
        });

        it('shows error toast when bulk accept fails', () => {
            cy.intercept('PATCH', '**/cases/document/*/redactions/bulk/', { statusCode: 500 }).as('failedBulk');
            mountRedactionComponent(mockDocument, mockRedactionsWithAdjacent);

            cy.contains('button', 'Accept').click();

            cy.wait('@failedBulk');
            cy.contains('Failed to accept suggestions. Please try again.').should('be.visible');
        });
    });
});
