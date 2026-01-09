import React from 'react';
import { RedactionContextManager } from './RedactionContextManager';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

describe('<RedactionContextManager />', () => {
    const redactionId = 'test-redaction-id-123';

    beforeEach(() => {
        // Set up default intercepts
        cy.intercept('POST', `**/cases/document/redaction/${redactionId}/context`, {
            statusCode: 200,
            body: { redaction: redactionId, text: 'Updated context' },
        }).as('updateContext');

        cy.intercept('DELETE', `**/cases/document/redaction/${redactionId}/context`, {
            statusCode: 204,
        }).as('deleteContext');
    });

    context('Rendering', () => {
        it('should not render when isEditing is false', () => {
            const onCancel = cy.spy().as('onCancel');
            const onContextSave = cy.spy().as('onContextSave');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Initial context' }}
                    isEditing={false}
                    onCancel={onCancel}
                    onContextSave={onContextSave}
                />,
                mountOpts
            );

            cy.get('body').should('not.contain', 'Context for Disclosure');
        });

        it('renders the text field when isEditing is true', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Some context' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').should('be.visible');
            cy.contains('This text will replace the redaction in the final export.').should('be.visible');
        });

        it('renders with initial context value', () => {
            const initialContext = 'This is the initial context.';
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: initialContext }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').should('have.value', initialContext);
        });

        it('renders empty when no context provided', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={null}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').should('have.value', '');
        });

        it('renders Save, Cancel, and Delete buttons', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Some context' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.contains('button', 'Save').should('be.visible');
            cy.contains('button', 'Cancel').should('be.visible');
            cy.get('[data-testid="DeleteIcon"]').should('be.visible');
        });
    });

    context('Editing', () => {
        it('allows editing the context text', () => {
            const initialContext = 'This is the initial context.';
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: initialContext }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').type(' More text.');
            cy.get('textarea[name="Context for Disclosure"]').should('have.value', `${initialContext} More text.`);
        });
    });

    context('Cancel', () => {
        it('calls onCancel when Cancel button is clicked', () => {
            const onCancel = cy.spy().as('onCancel');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Original text' }}
                    isEditing={true}
                    onCancel={onCancel}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.contains('button', 'Cancel').click();
            cy.get('@onCancel').should('have.been.calledOnce');
        });

        it('reverts text to initial value when Cancel is clicked', () => {
            const initialContext = 'Do not change me.';

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: initialContext }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').type(' I changed it.');
            cy.get('textarea[name="Context for Disclosure"]').should('have.value', `${initialContext} I changed it.`);
            cy.contains('button', 'Cancel').click();
            cy.get('textarea[name="Context for Disclosure"]').should('have.value', initialContext);
        });
    });

    context('Save', () => {
        it('calls updateRedactionContext API when Save is clicked', () => {
            const newContextText = 'This is the updated context.';

            cy.intercept('POST', `**/cases/document/redaction/${redactionId}/context`, {
                statusCode: 200,
                body: { redaction: redactionId, text: newContextText },
            }).as('updateContext');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Old context' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').clear().type(newContextText);
            cy.contains('button', 'Save').click();

            cy.wait('@updateContext').its('request.body').should('deep.include', { text: newContextText });
        });

        it('shows success toast when save succeeds', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Old context' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').clear().type('New context');
            cy.contains('button', 'Save').click();

            cy.wait('@updateContext');
            cy.contains('Context saved successfully.').should('be.visible');
        });

        it('calls onContextSave with redactionId and new text when save succeeds', () => {
            const onContextSave = cy.spy().as('onContextSave');
            const newText = 'Brand new context';

            cy.intercept('POST', `**/cases/document/redaction/${redactionId}/context`, {
                statusCode: 200,
                body: { redaction: redactionId, text: newText },
            }).as('updateContext');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Old context' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={onContextSave}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').clear().type(newText);
            cy.contains('button', 'Save').click();

            cy.wait('@updateContext');
            cy.get('@onContextSave').should('have.been.calledWith', redactionId, newText);
        });

        it('shows error alert when save fails', () => {
            cy.intercept('POST', `**/cases/document/redaction/${redactionId}/context`, {
                statusCode: 500,
                body: { detail: 'Server error' },
            }).as('updateContextFailed');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Old context' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').clear().type('New text');
            cy.contains('button', 'Save').click();

            cy.wait('@updateContextFailed');
            cy.get('[role="alert"]').should('be.visible');
            cy.contains('Failed to save context.').should('be.visible');
        });
    });

    context('Delete', () => {
        it('disables delete button when context is empty', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={null}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('[data-testid="DeleteIcon"]').parent('button').should('be.disabled');
        });

        it('enables delete button when context has text', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Some context' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('[data-testid="DeleteIcon"]').parent('button').should('not.be.disabled');
        });

        it('calls deleteRedactionContext API when delete button is clicked', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Context to delete' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('[data-testid="DeleteIcon"]').parent('button').click();

            cy.wait('@deleteContext');
        });

        it('shows success toast when delete succeeds', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Context to delete' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('[data-testid="DeleteIcon"]').parent('button').click();

            cy.wait('@deleteContext');
            cy.contains('Context deleted successfully.').should('be.visible');
        });

        it('calls onContextSave with null when delete succeeds', () => {
            const onContextSave = cy.spy().as('onContextSave');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Context to delete' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={onContextSave}
                />,
                mountOpts
            );

            cy.get('[data-testid="DeleteIcon"]').parent('button').click();

            cy.wait('@deleteContext');
            cy.get('@onContextSave').should('have.been.calledWith', redactionId, null);
        });

        it('clears the text field after successful delete', () => {
            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Context to delete' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').should('have.value', 'Context to delete');
            cy.get('[data-testid="DeleteIcon"]').parent('button').click();

            cy.wait('@deleteContext');
            cy.get('textarea[name="Context for Disclosure"]').should('have.value', '');
        });

        it('shows error alert when delete fails', () => {
            cy.intercept('DELETE', `**/cases/document/redaction/${redactionId}/context`, {
                statusCode: 500,
                body: { detail: 'Server error' },
            }).as('deleteContextFailed');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Context to delete' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('[data-testid="DeleteIcon"]').parent('button').click();

            cy.wait('@deleteContextFailed');
            cy.get('[role="alert"]').should('be.visible');
            cy.contains('Failed to delete context.').should('be.visible');
        });
    });

    context('Loading State', () => {
        it('shows loading spinner while saving', () => {
            cy.intercept('POST', `**/cases/document/redaction/${redactionId}/context`, {
                delay: 500,
                statusCode: 200,
                body: { redaction: redactionId, text: 'New text' },
            }).as('updateContextDelayed');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Old context' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('textarea[name="Context for Disclosure"]').clear().type('New text');
            cy.contains('button', 'Save').click();

            cy.get('[role="progressbar"]').should('be.visible');
        });

        it('shows loading spinner while deleting', () => {
            cy.intercept('DELETE', `**/cases/document/redaction/${redactionId}/context`, {
                delay: 500,
                statusCode: 204,
            }).as('deleteContextDelayed');

            cy.fullMount(
                <RedactionContextManager
                    redactionId={redactionId}
                    context={{ text: 'Context to delete' }}
                    isEditing={true}
                    onCancel={() => {}}
                    onContextSave={() => {}}
                />,
                mountOpts
            );

            cy.get('[data-testid="DeleteIcon"]').parent('button').click();

            cy.get('[role="progressbar"]').should('be.visible');
        });
    });
});
