import React, { useState } from 'react';
import { ManualRedactionPopover } from './ManualRedactionPopover';
import { Button } from '@mui/material';

const PopoverTestWrapper = ({ onRedact, onClose }) => {
    const [anchorEl, setAnchorEl] = useState(null);

    const handleClick = (event) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
        onClose();
    };

    return (
        <div>
            <Button onClick={handleClick}>Open Popover</Button>
            <ManualRedactionPopover
                anchorEl={anchorEl}
                onClose={handleClose}
                onRedact={onRedact}
            />
        </div>
    );
};

describe('<ManualRedactionPopover />', () => {
    let onRedactSpy;
    let onCloseSpy;

    beforeEach(() => {
        onRedactSpy = cy.spy().as('onRedactSpy');
        onCloseSpy = cy.spy().as('onCloseSpy');

        cy.mount(<PopoverTestWrapper onRedact={onRedactSpy} onClose={onCloseSpy} />);
        cy.contains('button', 'Open Popover').click();
        cy.get('[role="presentation"]').should('be.visible');
    });

    it('should render with the default redaction type selected', () => {
        cy.contains('label', 'Redaction Type').should('be.visible');
        cy.get('[role="combobox"]').contains('Third-Party PII').should('be.visible');
    });

    it('should call onRedact with the default type when "Redact" is clicked', () => {
        cy.contains('button', 'Redact').click();
        cy.get('@onRedactSpy').should('have.been.calledOnceWith', 'PII');
    });

    it('should allow changing the redaction type and call onRedact with the new type', () => {
        cy.get('[role="combobox"]').contains('Third-Party PII').click();
        cy.get('[role="listbox"]').contains('li', 'Operational Data').click();

        cy.contains('button', 'Redact').click();
        cy.get('@onRedactSpy').should('have.been.calledOnceWith', 'OP_DATA');
    });

    it('should call onClose when the "Cancel" button is clicked', () => {
        cy.contains('button', 'Cancel').click();
        cy.get('@onCloseSpy').should('have.been.calledOnce');
    });
});