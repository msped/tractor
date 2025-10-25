import React from 'react';
import { TrainingRunList } from '@/components/TrainingRunList';

describe('<TrainingRunList />', () => {
    const mockRuns = [
        {
            id: 1,
            created_at: '2024-05-22T10:00:00Z',
            model_name: 'model_20240522_100000',
            source: 'redactions',
            f1_score: 0.88123,
            precision: 0.91456,
            recall: 0.85,
        },
        {
            id: 2,
            created_at: '2024-05-21T09:00:00Z',
            model_name: 'model_20240521_090000',
            source: 'uploaded_documents',
            f1_score: null,
            precision: null,
            recall: null,
        },
    ];

    context('When runs are provided', () => {
        beforeEach(() => {
            cy.mount(<TrainingRunList runs={mockRuns} />);
        });

        it('renders the table with training run data', () => {
            cy.contains('h6', 'Training Run History').should('be.visible');

            cy.contains('tr', 'model_20240522_100000').within(() => {
                cy.contains('td', new Date(mockRuns[0].created_at).toLocaleString()).should('be.visible');
                cy.contains('td', 'redactions').should('be.visible');
                cy.contains('td', '88.12%').should('be.visible');
                cy.contains('td', '91.46%').should('be.visible');
                cy.contains('td', '85.00%').should('be.visible');
            });

            cy.contains('tr', 'model_20240521_090000').within(() => {
                cy.contains('td', new Date(mockRuns[1].created_at).toLocaleString()).should('be.visible');
                cy.contains('td', 'uploaded documents').should('be.visible');
                cy.get('td:contains("N/A")').should('have.length', 3);
            });
        });

        it('shows a tooltip with score explanations', () => {
            cy.contains('h6', 'Training Run History')
                .parent()
                .find('button')
                .trigger('mouseover');

            cy.get('[role="tooltip"]').should('be.visible');
            cy.contains('[role="tooltip"]', "These scores evaluate the model's performance.").should('be.visible');
            cy.contains('[role="tooltip"]', 'P (Precision):').should('be.visible');
            cy.contains('[role="tooltip"]', 'R (Recall):').should('be.visible');
            cy.contains('[role="tooltip"]', 'F1-Score:').should('be.visible');
        });
    });

    context('When no runs are provided', () => {
        it('renders a message indicating no training runs were found', () => {
            cy.mount(<TrainingRunList runs={[]} />);

            cy.get('tbody tr').should('have.length', 1);
            cy.contains('td', 'No training runs found.').should('be.visible');
        });
    });
});