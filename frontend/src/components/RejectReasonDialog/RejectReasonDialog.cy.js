import React from 'react';
import { RejectReasonDialog } from './RejectReasonDialog';

describe('<RejectReasonDialog />', () => {
    const mockRedaction = { id: 'redaction-123', text: 'sensitive information' };

    it('renders the dialog with correct content when open', () => {
        const onCloseSpy = cy.spy().as('onCloseSpy');
        const onSubmitSpy = cy.spy().as('onSubmitSpy');

        cy.mount(
            <RejectReasonDialog
                open={true}
                onClose={onCloseSpy}
                onSubmit={onSubmitSpy}
                redaction={mockRedaction}
            />
        );

        cy.contains('Reason for Rejection').should('be.visible');
        cy.contains(`"${mockRedaction.text}"`).should('be.visible');
        cy.get('button').contains('Submit').should('be.disabled');
        cy.get('button').contains('Cancel').should('be.enabled');
    });

    it('enables the submit button only when a reason is entered', () => {
        cy.mount(
            <RejectReasonDialog open={true} onClose={() => {}} onSubmit={() => {}} redaction={mockRedaction} />
        );

        cy.get('button').contains('Submit').should('be.disabled');

        // Type some text
        cy.get('textarea[id="reject-reason"]').type('This is not PII.');
        cy.get('button').contains('Submit').should('be.enabled');

        // Clear the text
        cy.get('textarea[id="reject-reason"]').clear();
        cy.get('button').contains('Submit').should('be.disabled');

        // Type only whitespace
        cy.get('textarea[id="reject-reason"]').type('   ');
        cy.get('button').contains('Submit').should('be.disabled');
    });

    it('calls onClose when the Cancel button is clicked', () => {
        const onCloseSpy = cy.spy().as('onCloseSpy');
        cy.mount(
            <RejectReasonDialog open={true} onClose={onCloseSpy} onSubmit={() => {}} redaction={mockRedaction} />
        );

        cy.get('button').contains('Cancel').click();
        cy.get('@onCloseSpy').should('have.been.calledOnce');
    });

    it('calls onSubmit with the correct data and then calls onClose', () => {
        const onCloseSpy = cy.spy().as('onCloseSpy');
        const onSubmitSpy = cy.spy().as('onSubmitSpy');
        const reasonText = 'User confirmed it is not relevant.';

        cy.mount(
            <RejectReasonDialog
                open={true}
                onClose={onCloseSpy}
                onSubmit={onSubmitSpy}
                redaction={mockRedaction}
            />
        );

        cy.get('textarea[id="reject-reason"]').type(reasonText);
        cy.get('button').contains('Submit').click();

        cy.get('@onSubmitSpy').should('have.been.calledOnceWith', mockRedaction.id, reasonText);
        cy.get('@onCloseSpy').should('have.been.calledOnce');
        cy.get('@onSubmitSpy').should('have.been.calledBefore', '@onCloseSpy');
    });
});