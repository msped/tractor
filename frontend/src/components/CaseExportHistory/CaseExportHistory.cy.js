import React from 'react';
import { SWRConfig } from 'swr';
import { CaseExportHistory } from './CaseExportHistory';

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
    case_reference: '250099',
    status: 'COMPLETED',
    export_status: 'COMPLETED',
};

const mockExports = [
    {
        id: 'exp-1',
        sequence: 1,
        label: 'Original disclosure',
        created_at: '2026-07-15T10:00:00Z',
        created_by: null,
        review: null,
        review_detail: null,
        export_file: '/media/exports/case-123/1/pkg.zip',
    },
    {
        id: 'exp-2',
        sequence: 2,
        label: 'Disclosure 2',
        created_at: '2026-07-16T12:30:00Z',
        created_by: 'alice',
        review: 'rev-1',
        review_detail: {
            id: 'rev-1',
            status: 'COMPLETED',
            outcome: 'DS challenge accepted',
            closed_by: 'alice',
            closed_at: '2026-07-16T12:00:00Z',
        },
        export_file: '/media/exports/case-123/2/pkg.zip',
    },
];

const baselineDiff = {
    baseline: true,
    base: null,
    counts: { added: 0, removed: 0, modified: 0 },
    added: [],
    removed: [],
    modified: [],
};

const changeDiff = {
    baseline: false,
    base: { sequence: 1, label: 'Original disclosure' },
    counts: { added: 1, removed: 0, modified: 0 },
    added: [
        {
            id: 'r-add',
            document_id: 'doc-1',
            filename: 'report.pdf',
            text: 'Bob',
            redaction_type: 'OP_DATA',
            is_accepted: false,
            decided_by: null,
            justification: null,
            context: null,
        },
    ],
    removed: [],
    modified: [],
};

const mount = (data = caseData) =>
    cy.fullMount(
        <TestWrapper>
            <CaseExportHistory caseData={data} />
        </TestWrapper>,
        mountOpts
    );

describe('<CaseExportHistory />', () => {
    it('renders each disclosure with its label and a download action', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: mockExports }).as('getExports');
        mount();
        cy.wait('@getExports');

        cy.contains('Disclosure History').should('be.visible');
        cy.contains('Original disclosure').should('be.visible');
        cy.contains('Disclosure 2').should('be.visible');
        cy.get('button[aria-label="Download Original disclosure"]').should('exist');
        cy.get('button[aria-label="Download Disclosure 2"]').should('exist');
        // The review-produced disclosure is badged.
        cy.contains('From review').should('be.visible');
    });

    it('shows an empty state when there are no exports', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: [] }).as('getExportsEmpty');
        mount();
        cy.wait('@getExportsEmpty');

        cy.contains('No disclosures have been generated').should('be.visible');
    });

    it('downloads the export file when the download button is clicked', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: mockExports }).as('getExports');
        cy.intercept('GET', '**/media/exports/case-123/1/pkg.zip', {
            statusCode: 200,
            body: 'zip-bytes',
        }).as('downloadExport');
        mount();
        cy.wait('@getExports');

        cy.get('button[aria-label="Download Original disclosure"]').click();
        cy.wait('@downloadExport');
    });

    it('expands a disclosure to reveal its outcome and diff', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: mockExports }).as('getExports');
        cy.intercept('GET', '**/cases/case-123/exports/exp-2/diff', { body: changeDiff }).as('getExp2Diff');
        mount();
        cy.wait('@getExports');

        cy.contains('Disclosure 2').click();
        cy.wait('@getExp2Diff');
        cy.contains('Review outcome').should('be.visible');
        cy.contains('DS challenge accepted').should('be.visible');
        cy.contains('Added').should('be.visible');
        cy.contains('Bob').should('be.visible');
    });

    it('shows a baseline note when expanding the first disclosure', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: mockExports }).as('getExports');
        cy.intercept('GET', '**/cases/case-123/exports/exp-1/diff', { body: baselineDiff }).as('getExp1Diff');
        mount();
        cy.wait('@getExports');

        cy.contains('Original disclosure').click();
        cy.wait('@getExp1Diff');
        cy.contains('nothing earlier to compare against').should('be.visible');
    });

    it('shows an in-progress row previewing staged changes during a review', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: mockExports }).as('getExports');
        cy.intercept('GET', '**/cases/case-123/diff', { body: changeDiff }).as('getLiveDiff');
        mount({ ...caseData, status: 'UNDER_REVIEW' });
        cy.wait('@getExports');

        cy.contains('Current review — changes not yet disclosed').should('be.visible');
        cy.contains('In progress').click();
        cy.wait('@getLiveDiff');
        cy.contains('Added').should('be.visible');
    });

    it('surfaces an unavailable note when a disclosure diff errors', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: mockExports }).as('getExports');
        cy.intercept('GET', '**/cases/case-123/exports/exp-2/diff', { statusCode: 404, body: {} }).as('getExp2Diff404');
        mount();
        cy.wait('@getExports');

        cy.contains('Disclosure 2').click();
        cy.wait('@getExp2Diff404');
        cy.contains('Change details are unavailable for this disclosure.').should('be.visible');
    });
});
