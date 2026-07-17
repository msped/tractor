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
        export_file: '/media/exports/case-123/1/pkg.zip',
    },
    {
        id: 'exp-2',
        sequence: 2,
        label: 'Disclosure 2',
        created_at: '2026-07-16T12:30:00Z',
        created_by: 'alice',
        review: null,
        export_file: '/media/exports/case-123/2/pkg.zip',
    },
];

describe('<CaseExportHistory />', () => {
    it('renders each export with its label and a download action', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: mockExports }).as('getExports');
        cy.fullMount(<TestWrapper><CaseExportHistory caseData={caseData} /></TestWrapper>, mountOpts);
        cy.wait('@getExports');

        cy.contains('Disclosure History').should('be.visible');
        cy.contains('Original disclosure').should('be.visible');
        cy.contains('Disclosure 2').should('be.visible');
        cy.get('button[aria-label="Download Original disclosure"]').should('exist');
        cy.get('button[aria-label="Download Disclosure 2"]').should('exist');
    });

    it('shows an empty state when there are no exports', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: [] }).as('getExportsEmpty');
        cy.fullMount(<TestWrapper><CaseExportHistory caseData={caseData} /></TestWrapper>, mountOpts);
        cy.wait('@getExportsEmpty');

        cy.contains('No disclosures have been generated').should('be.visible');
    });

    it('downloads the export file when the download button is clicked', () => {
        cy.intercept('GET', '**/cases/case-123/exports', { body: mockExports }).as('getExports');
        cy.intercept('GET', '**/media/exports/case-123/1/pkg.zip', {
            statusCode: 200,
            body: 'zip-bytes',
        }).as('downloadExport');
        cy.fullMount(<TestWrapper><CaseExportHistory caseData={caseData} /></TestWrapper>, mountOpts);
        cy.wait('@getExports');

        cy.get('button[aria-label="Download Original disclosure"]').click();
        cy.wait('@downloadExport');
    });
});
