import React from 'react';
import { SWRConfig } from 'swr';
import { CaseDisclosureDiff } from './CaseDisclosureDiff';

const mountOpts = {
    mockSession: {
        user: { id: '1', name: 'Test User', email: 'test@example.com' },
        session: { token: 'fake-token', userId: '1' },
    },
};

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

const caseData = {
    id: 'case-123',
    status: 'UNDER_REVIEW',
    export_status: 'COMPLETED',
    is_disclosed: true,
};

const mockDiff = {
    snapshot: {
        id: 'snap-1',
        created_at: '2026-07-16T12:30:00Z',
        export: { sequence: 1, label: 'Original disclosure' },
    },
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

const mount = () =>
    cy.fullMount(
        <TestWrapper>
            <CaseDisclosureDiff caseData={caseData} />
        </TestWrapper>,
        mountOpts
    );

describe('<CaseDisclosureDiff />', () => {
    it('renders added, removed and modified sections against the baseline', () => {
        cy.intercept('GET', '**/cases/case-123/diff', { body: mockDiff }).as('getDiff');
        mount();
        cy.wait('@getDiff');

        cy.contains('Changes Since Last Disclosure').should('be.visible');
        cy.contains('Compared against “Original disclosure”.').should('be.visible');

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

    it('shows a loading spinner before the diff resolves', () => {
        cy.intercept('GET', '**/cases/case-123/diff', {
            body: mockDiff,
            delay: 200,
        }).as('getDiffSlow');
        mount();

        cy.get('[role="progressbar"]').should('be.visible');
        cy.wait('@getDiffSlow');
        cy.contains('Added').should('be.visible');
    });

    it('shows a no-changes message when nothing differs', () => {
        cy.intercept('GET', '**/cases/case-123/diff', {
            body: {
                snapshot: { id: 'snap-1', created_at: '2026-07-16T12:30:00Z', export: null },
                counts: { added: 0, removed: 0, modified: 0 },
                added: [],
                removed: [],
                modified: [],
            },
        }).as('getDiffEmpty');
        mount();
        cy.wait('@getDiffEmpty');

        cy.contains('Compared against the last disclosure snapshot.').should('be.visible');
        cy.contains('No changes since the last disclosure.').should('be.visible');
    });

    it('shows an unavailable note when the diff endpoint errors', () => {
        cy.intercept('GET', '**/cases/case-123/diff', { statusCode: 404, body: {} }).as('getDiff404');
        mount();
        cy.wait('@getDiff404');

        cy.contains('The disclosure diff is unavailable for this case.').should('be.visible');
    });
});
