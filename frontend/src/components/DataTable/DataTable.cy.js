import React from 'react';
import { DataTable } from './DataTable';

describe('<DataTable />', () => {
    const mockRows = [
        { id: 'case-1', case_reference: 'REF001', data_subject_name: 'John Doe', status: 'OPEN', created_at: '2024-01-01T12:00:00Z', status_display: 'Open' },
        { id: 'case-2', case_reference: 'REF002', data_subject_name: 'Jane Smith', status: 'IN_PROGRESS', created_at: '2024-02-01T12:00:00Z', status_display: 'In Progress' },
        { id: 'case-3', case_reference: 'REF003', data_subject_name: 'Peter Jones', status: 'COMPLETED', created_at: '2024-03-01T12:00:00Z', status_display: 'Completed' },
        { id: 'case-4', case_reference: 'REF004', data_subject_name: 'Mary Williams', status: 'WITHDRAWN', created_at: '2024-04-01T12:00:00Z', status_display: 'Withdrawn' },
    ];

    const mountOpts = { mockSession: { access_token: 'fake-token' } };

    it('renders and applies initial filter correctly', () => {
        cy.fullMount(<DataTable rows={mockRows} />, mountOpts);

        cy.contains('button', 'Open / In Progress').should('have.class', 'MuiButton-contained');

        cy.contains('REF001').should('be.visible');
        cy.contains('REF002').should('be.visible');
        cy.contains('REF003').should('not.exist');
        cy.contains('REF004').should('not.exist');
    });

    it('renders cell content correctly', () => {
        cy.fullMount(<DataTable rows={mockRows} />, mountOpts);

        cy.contains('a', 'REF001').should('have.attr', 'href', '/cases/case-1');

        cy.contains('.MuiDataGrid-row', 'John Doe').within(() => {
            cy.contains('.MuiChip-root', 'Open').should('be.visible');
        });

        cy.contains('01/01/2024').should('be.visible');
    });

    it('navigates to new case page when "New Case" is clicked', () => {
        cy.fullMount(<DataTable rows={mockRows} />, mountOpts);

        cy.contains('a', 'New Case').should('have.attr', 'href', '/cases/new');
    });

    context('Toolbar Filtering', () => {
        beforeEach(() => {
            cy.fullMount(<DataTable rows={mockRows} />, mountOpts);
        });

        it('filters by "Completed / Closed" when button is clicked', () => {
            cy.contains('button', 'Completed / Closed').click();

            cy.contains('REF001').should('not.exist');
            cy.contains('REF002').should('not.exist');
            cy.contains('REF003').should('be.visible');
            cy.contains('REF004').should('not.exist');
        });

        it('filters by "Withdrawn" when button is clicked', () => {
            cy.contains('button', 'Withdrawn').click();

            cy.contains('REF001').should('not.exist');
            cy.contains('REF002').should('not.exist');
            cy.contains('REF003').should('not.exist');
            cy.contains('REF004').should('be.visible');
        });

        it('shows all rows when "All" button is clicked', () => {
            cy.contains('button', 'All').click();

            cy.contains('REF001').should('be.visible');
            cy.contains('REF002').should('be.visible');
            cy.contains('REF003').should('be.visible');
            cy.contains('REF004').should('be.visible');
        });

        it('filters correctly using the quick filter search box', () => {
            cy.contains('button', 'All').click();

            cy.get('input[role="searchbox"]').type('Peter');

            cy.contains('REF001').should('not.exist');
            cy.contains('REF003').should('be.visible');

            cy.get('button[aria-label="Clear search"]').click();

            cy.contains('REF001').should('be.visible');
            cy.contains('REF002').should('be.visible');
            cy.contains('REF003').should('be.visible');
            cy.contains('REF004').should('be.visible');
        });
    });
});