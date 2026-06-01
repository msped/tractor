import React from 'react';
import { DataTable } from './DataTable';

const makeResponse = (results) => ({
    count: results.length,
    next: null,
    previous: null,
    results,
});

const allCases = [
    { id: 'case-1', case_reference: 'REF001', data_subject_name: 'John Doe', status: 'OPEN', created_at: '2024-01-01T12:00:00Z', status_display: 'Open' },
    { id: 'case-2', case_reference: 'REF002', data_subject_name: 'Jane Smith', status: 'IN_PROGRESS', created_at: '2024-02-01T12:00:00Z', status_display: 'In Progress' },
    { id: 'case-3', case_reference: 'REF003', data_subject_name: 'Peter Jones', status: 'COMPLETED', created_at: '2024-03-01T12:00:00Z', status_display: 'Completed' },
    { id: 'case-4', case_reference: 'REF004', data_subject_name: 'Mary Williams', status: 'WITHDRAWN', created_at: '2024-04-01T12:00:00Z', status_display: 'Withdrawn' },
];

const openCases = allCases.filter((c) => ['OPEN', 'IN_PROGRESS', 'UNDER_REVIEW'].includes(c.status));

describe('<DataTable />', () => {
    const mountOpts = { mockSession: { access_token: 'fake-token' } };

    context('Initial load', () => {
        it('requests open/in-progress cases by default and renders them', () => {
            cy.intercept('GET', '**/cases*', (req) => {
                const url = new URL(req.url);
                const statusParam = url.searchParams.get('status');
                if (statusParam && statusParam.includes('OPEN')) {
                    req.reply(makeResponse(openCases));
                } else {
                    req.reply(makeResponse(allCases));
                }
            }).as('getCases');

            cy.fullMount(<DataTable />, mountOpts);
            cy.wait('@getCases');

            cy.contains('button', 'Open / In Progress').should('have.class', 'MuiButton-contained');
            cy.contains('REF001').should('be.visible');
            cy.contains('REF002').should('be.visible');
        });

        it('renders cell content correctly', () => {
            cy.intercept('GET', '**/cases*', makeResponse(openCases)).as('getCases');
            cy.fullMount(<DataTable />, mountOpts);
            cy.wait('@getCases');

            cy.contains('a', 'REF001').should('have.attr', 'href', '/cases/case-1');
            cy.contains('.MuiDataGrid-row', 'John Doe').within(() => {
                cy.contains('.MuiChip-root', 'Open').should('be.visible');
            });
            cy.contains('01/01/2024').should('be.visible');
        });
    });

    context('Toolbar filtering', () => {
        beforeEach(() => {
            cy.intercept('GET', '**/cases*', (req) => {
                const url = new URL(req.url);
                const statusParam = url.searchParams.get('status');
                if (!statusParam) {
                    req.reply(makeResponse(allCases));
                } else {
                    const statuses = statusParam.split(',');
                    req.reply(makeResponse(allCases.filter((c) => statuses.includes(c.status))));
                }
            }).as('getCases');

            cy.fullMount(<DataTable />, mountOpts);
            cy.wait('@getCases');
        });

        it('requests all cases when "All" is clicked', () => {
            cy.contains('button', 'All').click();
            cy.wait('@getCases').its('request.url').should('not.include', 'status=');
            cy.contains('button', 'All').should('have.class', 'MuiButton-contained');
            cy.contains('REF003').should('be.visible');
            cy.contains('REF004').should('be.visible');
        });

        it('requests completed/closed cases when button is clicked', () => {
            cy.contains('button', 'Completed / Closed').click();
            cy.wait('@getCases').its('request.url').should('include', 'COMPLETED');
            cy.contains('REF003').should('be.visible');
        });

        it('requests withdrawn cases when button is clicked', () => {
            cy.contains('button', 'Withdrawn').click();
            cy.wait('@getCases').its('request.url').should('include', 'WITHDRAWN');
            cy.contains('REF004').should('be.visible');
        });
    });

    context('Search', () => {
        beforeEach(() => {
            cy.intercept('GET', '**/cases*', (req) => {
                const url = new URL(req.url);
                const searchParam = url.searchParams.get('search');
                if (searchParam) {
                    req.reply(makeResponse(allCases.filter((c) =>
                        c.data_subject_name.toLowerCase().includes(searchParam.toLowerCase()) ||
                        c.case_reference.toLowerCase().includes(searchParam.toLowerCase())
                    )));
                } else {
                    req.reply(makeResponse(allCases));
                }
            }).as('getCases');

            cy.fullMount(<DataTable />, mountOpts);
            cy.wait('@getCases');
        });

        it('does not search with fewer than 3 characters', () => {
            cy.get('input[aria-label="Search"]').type('Pe');
            cy.wait(400);
            cy.get('@getCases.all').should('have.length', 1);
        });

        it('sends search request with 3+ characters after debounce', () => {
            cy.get('input[aria-label="Search"]').type('Pet');
            cy.wait('@getCases').its('request.url').should('include', 'search=Pet');
            cy.contains('REF003').should('be.visible');
        });

        it('clears search and resets results', () => {
            cy.get('input[aria-label="Search"]').type('Peter');
            cy.wait('@getCases');

            cy.get('button[aria-label="Clear search"]').click();
            cy.wait('@getCases').its('request.url').should('not.include', 'search=');
        });
    });
});
