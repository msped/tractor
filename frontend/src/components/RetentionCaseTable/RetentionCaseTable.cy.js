import React from 'react';
import { RetentionCaseTable } from './RetentionCaseTable';

const mockCases = [
    { id: 'uuid-1', case_reference: 'RET001', data_subject_name: 'Alice Smith', retention_review_date: '2025-01-01' },
    { id: 'uuid-2', case_reference: 'RET002', data_subject_name: 'Bob Jones', retention_review_date: '2025-02-01' },
];

describe('<RetentionCaseTable />', () => {
    it('renders all case rows', () => {
        cy.mount(<RetentionCaseTable cases={mockCases} selectedIds={new Set()} onSelectionChange={cy.stub()} onDeleteOne={cy.stub()} onDeleteMany={cy.stub()} isDeleting={false} />);
        cy.contains('RET001').should('be.visible');
        cy.contains('RET002').should('be.visible');
        cy.contains('Alice Smith').should('be.visible');
    });

    it('shows empty state when cases is empty', () => {
        cy.mount(<RetentionCaseTable cases={[]} selectedIds={new Set()} onSelectionChange={cy.stub()} onDeleteOne={cy.stub()} onDeleteMany={cy.stub()} isDeleting={false} />);
        cy.contains('No cases require review.').should('be.visible');
    });

    it('calls onDeleteOne with correct id when delete button clicked', () => {
        const onDeleteOne = cy.stub().as('deleteOne');
        cy.mount(<RetentionCaseTable cases={mockCases} selectedIds={new Set()} onSelectionChange={cy.stub()} onDeleteOne={onDeleteOne} onDeleteMany={cy.stub()} isDeleting={false} />);
        cy.get('[aria-label="delete RET001"]').click();
        cy.get('@deleteOne').should('have.been.calledWith', 'uuid-1');
    });

    it('renders a view link for each case', () => {
        cy.mount(<RetentionCaseTable cases={mockCases} selectedIds={new Set()} onSelectionChange={cy.stub()} onDeleteOne={cy.stub()} onDeleteMany={cy.stub()} isDeleting={false} />);
        cy.get('[aria-label="view RET001"]').should('have.attr', 'href', '/cases/uuid-1');
    });

    it('shows bulk delete button when rows are selected', () => {
        cy.mount(<RetentionCaseTable cases={mockCases} selectedIds={new Set(['uuid-1'])} onSelectionChange={cy.stub()} onDeleteOne={cy.stub()} onDeleteMany={cy.stub()} isDeleting={false} />);
        cy.contains('Delete selected (1)').should('be.visible');
    });

    it('does not show bulk delete button when nothing selected', () => {
        cy.mount(<RetentionCaseTable cases={mockCases} selectedIds={new Set()} onSelectionChange={cy.stub()} onDeleteOne={cy.stub()} onDeleteMany={cy.stub()} isDeleting={false} />);
        cy.contains('Delete selected').should('not.exist');
    });

    it('calls onDeleteMany with selected ids when bulk delete clicked', () => {
        const onDeleteMany = cy.stub().as('deleteMany');
        cy.mount(<RetentionCaseTable cases={mockCases} selectedIds={new Set(['uuid-1', 'uuid-2'])} onSelectionChange={cy.stub()} onDeleteOne={cy.stub()} onDeleteMany={onDeleteMany} isDeleting={false} />);
        cy.contains('Delete selected (2)').click();
        cy.get('@deleteMany').should('have.been.called');
    });

    it('calls onSelectionChange when a row checkbox is clicked', () => {
        const onSelectionChange = cy.stub().as('selectionChange');
        cy.mount(<RetentionCaseTable cases={mockCases} selectedIds={new Set()} onSelectionChange={onSelectionChange} onDeleteOne={cy.stub()} onDeleteMany={cy.stub()} isDeleting={false} />);
        cy.get('[aria-label="select RET001"]').click();
        cy.get('@selectionChange').should('have.been.called');
    });
});
