import React from 'react';
import { RedactionContextManager } from './RedactionContextManager';
import * as redactionService from '@/services/redactionService';

describe('<RedactionContextManager />', () => {
  const redactionId = 'test-redaction-id-123';

  it('should not render when isEditing is false', () => {
    const onCancel = cy.spy().as('onCancel');
    const onSaveSuccess = cy.spy().as('onSaveSuccess');

    cy.mount(
      <RedactionContextManager
        redactionId={redactionId}
        context={{ text: 'Initial context' }}
        isEditing={false}
        onCancel={onCancel}
        onSaveSuccess={onSaveSuccess}
      />
    );

    cy.get('body').should('not.contain', 'Context for Disclosure');
  });

  it('renders with initial context and allows editing', () => {
    const initialContext = 'This is the initial context.';
    cy.mount(
      <RedactionContextManager
        redactionId={redactionId}
        context={{ text: initialContext }}
        isEditing={true}
        onCancel={() => {}}
        onSaveSuccess={() => {}}
      />
    );

    cy.get('textarea[name="Context for Disclosure"]').should('have.value', initialContext);
    cy.get('textarea[name="Context for Disclosure"]').type(' More text.');
    cy.get('textarea[name="Context for Disclosure"]').should('have.value', `${initialContext} More text.`);
  });

  it('calls onCancel and reverts text when Cancel button is clicked', () => {
    const onCancel = cy.spy().as('onCancel');
    const initialContext = 'Do not change me.';

    cy.mount(
      <RedactionContextManager
        redactionId={redactionId}
        context={{ text: initialContext }}
        isEditing={true}
        onCancel={onCancel}
        onSaveSuccess={() => {}}
      />
    );

    cy.get('textarea[name="Context for Disclosure"]').type(' I changed it.');
    cy.contains('button', 'Cancel').click();
    cy.get('@onCancel').should('have.been.calledOnce');
    cy.get('textarea[name="Context for Disclosure"]').should('have.value', initialContext);
  });

// Fix on Request Rework, next job
//   it.only('successfully saves new context', () => {
//     const onSaveSuccess = cy.spy().as('onSaveSuccess');
//     const newContextText = 'This is the updated context.';

//     cy.stub(redactionService, 'updateRedactionContext')
//       .as('updateRedactionContextStub')
//       .resolves({
//         redaction: redactionId,
//         text: newContextText,
//       });

//     cy.mount(
//       <RedactionContextManager
//         redactionId={redactionId}
//         context={{ text: 'Old context' }}
//         isEditing={true}
//         onCancel={() => {}}
//         onSaveSuccess={onSaveSuccess}
//       />
//     );

//     cy.get('textarea[name="Context for Disclosure"]').clear().type(newContextText);
//     cy.contains('button', 'Save').click();

//     cy.get('@updateRedactionContextStub').should(
//       'have.been.calledWith',
//       redactionId,
//       { text: newContextText }
//     );
//     cy.get('@onSaveSuccess').should('have.been.calledWith', redactionId, newContextText);
//     cy.get('body').should('contain', 'Context saved successfully.');
//   });

//   it('successfully deletes context', () => {
//     const onSaveSuccess = cy.spy().as('onSaveSuccess');

//     cy.stub(redactionService, 'deleteRedactionContent')
//       .as('deleteRedactionContentStub')
//       .resolves();
//     cy.mount(
//       <RedactionContextManager
//         redactionId={redactionId}
//         context={{ text: 'Some context to delete' }}
//         isEditing={true}
//         onCancel={() => {}}
//         onSaveSuccess={onSaveSuccess}
//       />
//     );

//     cy.get('[data-testid="DeleteIcon"]').click();
//     cy.get('@deleteRedactionContentStub').should('have.been.calledWith', redactionId);
//     cy.get('@onSaveSuccess').should('have.been.calledWith', redactionId, '');
//     cy.get('body').should('contain', 'Context deleted successfully.');
//     cy.get('textarea[name="Context for Disclosure"]').should('have.value', '');
//   });

  it('shows an error message when saving fails', () => {
    cy.stub(redactionService, 'updateRedactionContext')
      .as('updateRedactionContextStub')
      .rejects(new Error('API Error'));

    cy.mount(
       <RedactionContextManager
        redactionId={redactionId}
        context={{ text: 'Old context' }}
        isEditing={true}
        onCancel={() => {}}
        onSaveSuccess={() => {}}
      />
    );

    cy.get('textarea[name="Context for Disclosure"]').clear().type('New text');
    cy.contains('button', 'Save').click();

    cy.get('.MuiAlert-root').should('be.visible');
    cy.get('.MuiAlert-root').should('contain', 'Failed to save context.');
  });
});