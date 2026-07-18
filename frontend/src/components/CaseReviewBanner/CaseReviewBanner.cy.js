import React from 'react';
import { CaseReviewBanner } from './CaseReviewBanner';

const mountOpts = {
    mockSession: {
        user: { id: '1', name: 'Test User', email: 'test@example.com' },
        session: { token: 'fake-token', userId: '1' },
    },
};

const disclosedCase = {
    id: 'case-123',
    case_reference: '250099',
    status: 'COMPLETED',
    is_disclosed: true,
    active_review: null,
};

describe('<CaseReviewBanner />', () => {
    it('renders nothing for a case that has never been disclosed', () => {
        cy.fullMount(
            <CaseReviewBanner caseData={{ ...disclosedCase, is_disclosed: false }} />,
            mountOpts
        );
        cy.get('.MuiAlert-root').should('not.exist');
    });

    it('offers an Open Review action on a disclosed, locked case', () => {
        cy.fullMount(<CaseReviewBanner caseData={disclosedCase} />, mountOpts);

        cy.contains('Disclosed & locked').should('be.visible');
        cy.contains('button', 'Open Review').should('be.visible');
    });

    it('opens a review and refreshes when the action is clicked', () => {
        cy.intercept('POST', '**/cases/case-123/reviews', {
            statusCode: 200,
            body: { id: 'rev-1', status: 'OPEN' },
        }).as('openReview');
        const onUpdate = cy.stub().as('onUpdate');

        cy.fullMount(
            <CaseReviewBanner caseData={disclosedCase} onUpdate={onUpdate} />,
            mountOpts
        );

        cy.contains('button', 'Open Review').click();
        cy.wait('@openReview');
        cy.get('@onUpdate').should('have.been.called');
    });

    it('keeps the action available when opening the review fails', () => {
        cy.intercept('POST', '**/cases/case-123/reviews', {
            statusCode: 500,
            body: { detail: 'boom' },
        }).as('openReviewFail');
        const onUpdate = cy.stub().as('onUpdate');

        cy.fullMount(
            <CaseReviewBanner caseData={disclosedCase} onUpdate={onUpdate} />,
            mountOpts
        );

        cy.contains('button', 'Open Review').click();
        cy.wait('@openReviewFail');
        cy.get('@onUpdate').should('not.have.been.called');
        cy.contains('button', 'Open Review').should('be.visible');
    });

    it('shows the unlocked banner while a review is open', () => {
        cy.fullMount(
            <CaseReviewBanner
                caseData={{
                    ...disclosedCase,
                    status: 'UNDER_REVIEW',
                    active_review: { id: 'rev-1', status: 'OPEN' },
                }}
            />,
            mountOpts
        );

        cy.contains('Under internal review — unlocked').should('be.visible');
        cy.contains('button', 'Open Review').should('not.exist');
    });
});
