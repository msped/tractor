import React from 'react';
import { DisclosureDiffView } from './DisclosureDiffView';

const diffWithChanges = {
    baseline: false,
    counts: { added: 1, removed: 1, modified: 1 },
    added: [
        {
            id: 'r-add',
            document_id: 'doc-1',
            filename: 'report.pdf',
            // Long text exercises the truncation path.
            text: 'Bob '.repeat(40),
            redaction_type: 'OP_DATA',
            is_accepted: false,
            decided_by: null,
            justification: null,
            context: null,
        },
    ],
    removed: [
        {
            id: 'r-rem',
            document_id: 'doc-1',
            filename: 'report.pdf',
            // Empty text exercises the "(empty)" fallback.
            text: '',
            redaction_type: 'PII',
            is_accepted: true,
            decided_by: 'HUMAN',
            justification: null,
            context: null,
        },
    ],
    modified: [
        {
            id: 'r-mod',
            document_id: 'doc-2',
            filename: 'notes.docx',
            text: 'Alice',
            redaction_type: 'OP_DATA',
            is_accepted: false,
            decided_by: 'HUMAN',
            justification: 'not needed',
            context: 'a witness',
            changes: {
                is_accepted: { from: true, to: false },
                redaction_type: { from: 'PII', to: 'OP_DATA' },
                justification: { from: null, to: 'not needed' },
                context: { from: null, to: 'a witness' },
            },
        },
    ],
};

describe('<DisclosureDiffView />', () => {
    it('renders added, removed and modified sections with change lines', () => {
        cy.fullMount(<DisclosureDiffView diff={diffWithChanges} />);

        cy.contains('Added').should('be.visible');
        cy.contains('Bob').should('be.visible');
        cy.contains('report.pdf · Operational').should('be.visible');

        cy.contains('Removed').should('be.visible');

        cy.contains('Modified').should('be.visible');
        cy.contains('Alice').should('be.visible');
        cy.contains('Decision: Accepted → Not accepted').should('be.visible');
        cy.contains('Type: Third-party PII → Operational').should('be.visible');
        cy.contains('Justification: — → not needed').should('be.visible');
        cy.contains('Context: — → a witness').should('be.visible');
        // Long added text is truncated with an ellipsis.
        cy.contains('…').should('be.visible');
        // Empty removed text falls back to a placeholder.
        cy.contains('(empty)').should('be.visible');
    });

    it('shows a baseline message for the original disclosure', () => {
        cy.fullMount(
            <DisclosureDiffView
                diff={{
                    baseline: true,
                    base: null,
                    counts: { added: 0, removed: 0, modified: 0 },
                    added: [],
                    removed: [],
                    modified: [],
                }}
            />
        );
        cy.contains('Original disclosure — nothing earlier to compare against.').should(
            'be.visible'
        );
    });

    it('shows a no-changes message when nothing differs', () => {
        cy.fullMount(
            <DisclosureDiffView
                diff={{
                    baseline: false,
                    counts: { added: 0, removed: 0, modified: 0 },
                    added: [],
                    removed: [],
                    modified: [],
                }}
            />
        );
        cy.contains('No redaction changes in this disclosure.').should('be.visible');
    });

    it('renders nothing when there is no diff', () => {
        cy.fullMount(
            <div data-testid="wrap">
                <DisclosureDiffView diff={null} />
            </div>
        );
        cy.get('[data-testid="wrap"]').should('be.empty');
    });
});
