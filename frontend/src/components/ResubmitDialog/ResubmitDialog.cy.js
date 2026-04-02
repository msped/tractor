import React from 'react';
import { ResubmitDialog } from './ResubmitDialog';

describe('<ResubmitDialog />', () => {
    it('renders title, content, and action buttons when open', () => {
        cy.mount(<ResubmitDialog open={true} onClose={cy.stub()} onConfirm={cy.stub()} isConfirming={false} />);
        cy.contains('Resubmit Document').should('be.visible');
        cy.contains('This will delete all current redactions').should('be.visible');
        cy.contains('button', 'Cancel').should('be.visible');
        cy.contains('button', 'Resubmit').should('be.visible');
    });

    it('calls onClose when Cancel is clicked', () => {
        const onClose = cy.stub().as('onClose');
        cy.mount(<ResubmitDialog open={true} onClose={onClose} onConfirm={cy.stub()} isConfirming={false} />);
        cy.contains('button', 'Cancel').click();
        cy.get('@onClose').should('have.been.calledOnce');
    });

    it('calls onConfirm when Resubmit is clicked', () => {
        const onConfirm = cy.stub().as('onConfirm');
        cy.mount(<ResubmitDialog open={true} onClose={cy.stub()} onConfirm={onConfirm} isConfirming={false} />);
        cy.contains('button', 'Resubmit').click();
        cy.get('@onConfirm').should('have.been.calledOnce');
    });

    it('shows spinner and disables both buttons when isConfirming is true', () => {
        cy.mount(<ResubmitDialog open={true} onClose={cy.stub()} onConfirm={cy.stub()} isConfirming={true} />);
        cy.get('[role="progressbar"]').should('exist');
        cy.contains('button', 'Cancel').should('be.disabled');
        cy.get('button[disabled]').find('[role="progressbar"]').should('exist');
    });

    it('does not render dialog content when open is false', () => {
        cy.mount(<ResubmitDialog open={false} onClose={cy.stub()} onConfirm={cy.stub()} isConfirming={false} />);
        cy.get('[role="dialog"]').should('not.exist');
    });
});
