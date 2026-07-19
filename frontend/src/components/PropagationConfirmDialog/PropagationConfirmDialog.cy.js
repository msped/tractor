import React from 'react';
import { PropagationConfirmDialog } from './PropagationConfirmDialog';

const mountOpts = {
    mockSession: {
        user: { id: '1', name: 'Test User', email: 'test@example.com' },
        session: { token: 'fake-token', userId: '1' },
    },
};

const preview = {
    term: 'Alice',
    total_matches: 3,
    affected_documents: [
        { document_id: 'd1', filename: 'letter.pdf', match_count: 2 },
        { document_id: 'd2', filename: 'notes.docx', match_count: 1 },
    ],
};

describe('<PropagationConfirmDialog />', () => {
    it('renders nothing when closed', () => {
        cy.fullMount(
            <PropagationConfirmDialog open={false} preview={preview} onConfirm={() => {}} onCancel={() => {}} />,
            mountOpts
        );
        cy.get('[role="dialog"]').should('not.exist');
    });

    it('summarises the affected documents and matches', () => {
        cy.fullMount(
            <PropagationConfirmDialog open preview={preview} onConfirm={() => {}} onCancel={() => {}} />,
            mountOpts
        );

        cy.contains('"Alice"').should('be.visible');
        cy.contains('3 further occurrences').should('be.visible');
        cy.contains('2 other documents').should('be.visible');
        cy.contains('letter.pdf').should('be.visible');
        cy.contains('2 matches').should('be.visible');
        cy.contains('notes.docx').should('be.visible');
        cy.contains('1 match').should('be.visible');
    });

    it('calls onConfirm when Propagate is clicked', () => {
        const onConfirm = cy.stub().as('onConfirm');
        cy.fullMount(
            <PropagationConfirmDialog open preview={preview} onConfirm={onConfirm} onCancel={() => {}} />,
            mountOpts
        );

        cy.contains('button', 'Propagate').click();
        cy.get('@onConfirm').should('have.been.called');
    });

    it('calls onCancel when Cancel is clicked', () => {
        const onCancel = cy.stub().as('onCancel');
        cy.fullMount(
            <PropagationConfirmDialog open preview={preview} onConfirm={() => {}} onCancel={onCancel} />,
            mountOpts
        );

        cy.contains('button', 'Cancel').click();
        cy.get('@onCancel').should('have.been.called');
    });

    it('disables the buttons while applying', () => {
        cy.fullMount(
            <PropagationConfirmDialog open preview={preview} loading onConfirm={() => {}} onCancel={() => {}} />,
            mountOpts
        );

        cy.contains('button', 'Propagate').should('be.disabled');
        cy.contains('button', 'Cancel').should('be.disabled');
    });

    it('handles a null preview without crashing', () => {
        cy.fullMount(
            <PropagationConfirmDialog open preview={null} onConfirm={() => {}} onCancel={() => {}} />,
            mountOpts
        );
        cy.get('[role="dialog"]').should('be.visible');
    });
});
