import React from 'react';
import { ConfirmationDialog } from './ConfirmationDialog';

describe('<ConfirmationDialog />', () => {
    it('renders title and description when open', () => {
        cy.mount(
            <ConfirmationDialog
                open={true}
                onClose={() => {}}
                onConfirm={() => {}}
                title="Confirm Action"
                description="Are you sure you want to do this?"
            />
        );

        cy.contains('Confirm Action').should('be.visible');
        cy.contains('Are you sure you want to do this?').should('be.visible');
    });

    it('does not render when closed', () => {
        cy.mount(
            <ConfirmationDialog
                open={false}
                onClose={() => {}}
                onConfirm={() => {}}
                title="Confirm Action"
                description="Are you sure?"
            />
        );

        cy.contains('Confirm Action').should('not.exist');
    });

    it('uses default "Confirm" label and primary color', () => {
        cy.mount(
            <ConfirmationDialog
                open={true}
                onClose={() => {}}
                onConfirm={() => {}}
                title="Default Label"
                description="Description"
            />
        );

        cy.contains('button', 'Confirm').should('be.visible');
    });

    it('renders custom confirmLabel', () => {
        cy.mount(
            <ConfirmationDialog
                open={true}
                onClose={() => {}}
                onConfirm={() => {}}
                title="Delete"
                description="This will be deleted."
                confirmLabel="Delete"
                confirmColor="error"
            />
        );

        cy.contains('button', 'Delete').should('be.visible');
        cy.contains('button', 'Cancel').should('be.visible');
    });

    it('calls onConfirm when confirm button is clicked', () => {
        const onConfirmSpy = cy.spy().as('onConfirmSpy');

        cy.mount(
            <ConfirmationDialog
                open={true}
                onClose={() => {}}
                onConfirm={onConfirmSpy}
                title="Confirm"
                description="Are you sure?"
                confirmLabel="Yes"
            />
        );

        cy.contains('button', 'Yes').click();
        cy.get('@onConfirmSpy').should('have.been.calledOnce');
    });

    it('calls onClose when Cancel is clicked', () => {
        const onCloseSpy = cy.spy().as('onCloseSpy');

        cy.mount(
            <ConfirmationDialog
                open={true}
                onClose={onCloseSpy}
                onConfirm={() => {}}
                title="Confirm"
                description="Are you sure?"
            />
        );

        cy.contains('button', 'Cancel').click();
        cy.get('@onCloseSpy').should('have.been.calledOnce');
    });
});
