import React from 'react';
import { ExemptionTemplatesCard } from './ExemptionTemplatesCard';
import * as redactionService from '@/services/redactionService';

const mockTemplates = [
    { id: 1, name: 'S.40 - Personal Information', description: 'Personal data exemption' },
    { id: 2, name: 'S.42 - Legal Privilege', description: '' },
];

describe('<ExemptionTemplatesCard />', () => {
    beforeEach(() => {
        cy.stub(redactionService, 'getExemptionTemplates').resolves(mockTemplates);
        cy.stub(redactionService, 'createExemptionTemplate').resolves({ id: 3, name: 'S.43 - National Security', description: '' });
        cy.stub(redactionService, 'deleteExemptionTemplate').resolves(true);
    });

    it('renders the card title and description', () => {
        cy.mount(<ExemptionTemplatesCard />);
        cy.contains('Exemption Templates').should('be.visible');
        cy.contains('Configurable rejection reasons').should('be.visible');
    });

    it('displays templates returned from the API', () => {
        cy.mount(<ExemptionTemplatesCard />);
        cy.contains('S.40 - Personal Information').should('be.visible');
        cy.contains('Personal data exemption').should('be.visible');
        cy.contains('S.42 - Legal Privilege').should('be.visible');
        cy.contains('—').should('be.visible');
    });

    it('shows empty state when no templates exist', () => {
        redactionService.getExemptionTemplates.resolves([]);
        cy.mount(<ExemptionTemplatesCard />);
        cy.contains('No exemption templates configured.').should('be.visible');
    });

    it('shows the add form when Add is clicked', () => {
        cy.mount(<ExemptionTemplatesCard />);
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').should('be.visible');
        cy.get('input[aria-label="template description"]').should('be.visible');
        cy.get('button').contains('Save').should('be.disabled');
    });

    it('enables Save only when name is entered', () => {
        cy.mount(<ExemptionTemplatesCard />);
        cy.get('button').contains('Add').click();
        cy.get('button').contains('Save').should('be.disabled');
        cy.get('input[aria-label="template name"]').type('S.43 - National Security');
        cy.get('button').contains('Save').should('be.enabled');
    });

    it('submits the new template and closes the form', () => {
        cy.mount(<ExemptionTemplatesCard />);
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').type('S.43 - National Security');
        cy.get('button').contains('Save').click();
        cy.wrap(redactionService.createExemptionTemplate).should('have.been.calledOnce');
        cy.get('input[aria-label="template name"]').should('not.exist');
    });

    it('cancels the add form without submitting', () => {
        cy.mount(<ExemptionTemplatesCard />);
        cy.get('button').contains('Add').click();
        cy.get('input[aria-label="template name"]').type('Something');
        cy.get('button').contains('Cancel').click();
        cy.get('input[aria-label="template name"]').should('not.exist');
        cy.wrap(redactionService.createExemptionTemplate).should('not.have.been.called');
    });

    it('opens a confirmation dialog before deleting', () => {
        cy.mount(<ExemptionTemplatesCard />);
        cy.get(`button[aria-label="delete S.40 - Personal Information"]`).click();
        cy.contains('Delete Exemption Template').should('be.visible');
        cy.contains('S.40 - Personal Information').should('be.visible');
    });

    it('deletes a template after confirmation', () => {
        cy.mount(<ExemptionTemplatesCard />);
        cy.get(`button[aria-label="delete S.40 - Personal Information"]`).click();
        cy.get('button').contains('Delete').last().click();
        cy.wrap(redactionService.deleteExemptionTemplate).should('have.been.calledOnceWith', 1);
    });
});
