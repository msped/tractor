import React from 'react';
import { CaseInformation } from '@/components/CaseInformation';
import apiClient from '@/api/apiClient';

const mockCaseOpen = {
    id: 1,
    case_reference: 'CASE-001',
    status: 'OPEN',
    status_display: 'Open',
    data_subject_name: 'John Doe',
    data_subject_dob: '1990-01-15T00:00:00Z',
    created_at: '2023-10-27T10:00:00Z',
    retention_review_date: '2025-10-27T00:00:00Z',
};

const mockCaseCompleted = {
    ...mockCaseOpen,
    id: 2,
    status: 'COMPLETED',
    status_display: 'Completed',
};

const mockSession = {
    access_token: 'test-token',
    expires: '2100-01-01T00:00:00Z',
};


describe('<CaseInformation />', () => {
    let onUpdateSpy;

    beforeEach(() => {
        onUpdateSpy = cy.stub().as('onUpdate');
        cy.stub(apiClient, 'patch').as('updateCase').resolves({ data: {} });
        cy.stub(apiClient, 'delete').as('deleteCase').resolves({});
    });

    it('renders case details correctly', () => {
        cy.fullMount(
            <CaseInformation caseObject={mockCaseOpen} onUpdate={onUpdateSpy} />,
            { mockSession: mockSession }
        );

        cy.contains('Case Details').should('be.visible');
        cy.contains('CASE-001').should('be.visible');
        cy.contains('Open').should('be.visible');
        cy.contains('John Doe').should('be.visible');
        cy.contains('15/01/1990').should('be.visible');
        cy.contains('27/10/2023').should('be.visible');
        cy.contains('27/10/2025').should('be.visible');
    });

    it('shows loading state when caseObject is null', () => {
        cy.fullMount(
            <CaseInformation caseObject={null} onUpdate={onUpdateSpy} />,
            { mockSession: mockSession }
        );
        cy.contains('Loading case information...').should('be.visible');
    });

    it('disables edit and action buttons for finalised cases', () => {
        cy.fullMount(
            <CaseInformation caseObject={mockCaseCompleted} onUpdate={onUpdateSpy} />,
            { mockSession: mockSession }
        );

        cy.get('button[aria-label="case actions"]').should('be.disabled');
        cy.get('button[aria-label="settings"]').should('be.disabled');
    });

    context('Editing Case', () => {
        beforeEach(() => {
            cy.fullMount(
                <CaseInformation caseObject={mockCaseOpen} onUpdate={onUpdateSpy} />,
                { mockSession: mockSession }
            );
            cy.get('button[aria-label="settings"]').click();
        });

        it('opens the edit dialog with pre-filled data', () => {
            cy.contains('Edit Case Details').should('be.visible');
            cy.get('input[name="case_reference"]').should('have.value', 'CASE-001');
            cy.get('input[name="data_subject_name"]').should('have.value', 'John Doe');
            cy.get('input[name="data_subject_dob"]').should('have.value', '1990-01-15');
            cy.get('input[name="retention_review_date"]').should('have.value', '2025-10-27');
        });

        it('allows updating case details and calls onUpdate', () => {
            cy.get('input[name="case_reference"]').clear().type('CASE-001-UPDATED');
            cy.get('button').contains('Save').click();

            cy.get('@updateCase').should('have.been.calledWith',
                `/cases/${mockCaseOpen.id}`,
                Cypress.sinon.match.has('case_reference', 'CASE-001-UPDATED'),
                Cypress.sinon.match.object
            );

            cy.contains('Case updated.').should('be.visible');
            cy.get('@onUpdate').should('have.been.calledOnce');
            cy.contains('Edit Case Details').should('not.exist');
        });

        it('closes the dialog on cancel', () => {
            cy.get('button').contains('Cancel').click();
            cy.contains('Edit Case Details').should('not.exist');
        });
    });

    context('Changing Case Status', () => {
        beforeEach(() => {
            cy.fullMount(
                <CaseInformation caseObject={mockCaseOpen} onUpdate={onUpdateSpy} />,
                { mockSession: mockSession}
            );
            cy.get('button[aria-label="case actions"]').click();
        });

        it('opens the status menu', () => {
            cy.get('ul[role="menu"]').should('be.visible');
            cy.get('li[role="menuitem"]').contains('Mark as Completed').should('be.visible');
            cy.get('li[role="menuitem"]').contains('Mark as Closed').should('be.visible');
            cy.get('li[role="menuitem"]').contains('Mark as Withdrawn').should('be.visible');
        });

        it('updates the status to Completed and calls onUpdate', () => {
            cy.get('li[role="menuitem"]').contains('Mark as Completed').click();

            cy.get('@updateCase').should('have.been.calledWith',
                `/cases/${mockCaseOpen.id}`,
                { status: 'COMPLETED' },
                Cypress.sinon.match.object
            );

            cy.contains('Case status updated.').should('be.visible');
            cy.get('@onUpdate').should('have.been.calledOnce');
            cy.get('ul[role="menu"]').should('not.exist');
        });

        it('updates the status to Closed and calls onUpdate', () => {
            cy.get('li[role="menuitem"]').contains('Mark as Closed').click();

            cy.get('@updateCase').should('have.been.calledWith',
                `/cases/${mockCaseOpen.id}`,
                { status: 'CLOSED' },
                Cypress.sinon.match.object
            );

            cy.contains('Case status updated.').should('be.visible');
            cy.get('@onUpdate').should('have.been.calledOnce');
        });
    });

    context('Deleting Case', () => {
        beforeEach(() => {
            cy.fullMount(
                <CaseInformation caseObject={mockCaseOpen} onUpdate={onUpdateSpy} />,
                { mockSession: mockSession}
            );
            cy.get('button[aria-label="settings"]').click();
            cy.get('button').contains('Delete Case').click();
        });

        it('opens the delete confirmation dialog', () => {
            cy.contains('Confirm Deletion').should('be.visible');
            cy.contains('Are you sure you want to delete this case?').should('be.visible');
            cy.contains('Edit Case Details').should('not.exist');
        });

        it('deletes the case and navigates on confirmation', () => {
            cy.get('button').contains('Delete').click();

            cy.get('@deleteCase').should('have.been.calledWith',
                `/cases/${mockCaseOpen.id}`,
                Cypress.sinon.match.object
            );

            cy.contains('Case deleted.').should('be.visible');
            cy.get('@router:push').should('have.been.calledWith', '/cases');
        });

        it('cancels deletion and re-opens the edit dialog', () => {
            // The first button is the cancel button in the DialogActions
            cy.get('div[role="dialog"]').find('button').contains('Cancel').click();

            cy.contains('Confirm Deletion').should('not.exist');
            cy.contains('Edit Case Details').should('be.visible');
        });
    });

    it('falls back to router.refresh if onUpdate is not provided', () => {
        cy.fullMount(
            <CaseInformation caseObject={mockCaseOpen} />,
            { mockSession: mockSession}
        );

        cy.get('button[aria-label="settings"]').click();
        cy.get('input[name="case_reference"]').clear().type('NEW-REF');
        cy.get('button').contains('Save').click();

        cy.get('@router:refresh').should('have.been.calledOnce');
    });
});