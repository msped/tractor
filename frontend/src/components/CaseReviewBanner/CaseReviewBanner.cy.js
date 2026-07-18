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

    const underReviewCase = {
        ...disclosedCase,
        status: 'UNDER_REVIEW',
        active_review: { id: 'rev-1', status: 'OPEN' },
    };

    it('shows the unlocked banner while a review is open', () => {
        cy.fullMount(
            <CaseReviewBanner caseData={underReviewCase} />,
            mountOpts
        );

        cy.contains('Under internal review — unlocked').should('be.visible');
        cy.contains('button', 'Open Review').should('not.exist');
        cy.contains('button', 'Complete Review').should('be.visible');
        cy.contains('button', 'Abandon Review').should('be.visible');
    });

    it('requires an outcome before completing a review', () => {
        cy.fullMount(
            <CaseReviewBanner caseData={underReviewCase} />,
            mountOpts
        );

        cy.contains('button', 'Complete Review').click();
        cy.contains('Complete review').should('be.visible');
        // Confirm is disabled until an outcome is written.
        cy.get('.MuiDialogActions-root')
            .contains('button', 'Complete')
            .should('be.disabled');
        cy.get('#review-outcome').type('Disclosure amended after challenge');
        cy.get('.MuiDialogActions-root')
            .contains('button', 'Complete')
            .should('not.be.disabled');
    });

    it('completes a review and refreshes', () => {
        cy.intercept('POST', '**/cases/case-123/reviews/complete', {
            statusCode: 200,
            body: { id: 'rev-1', status: 'COMPLETED' },
        }).as('completeReview');
        const onUpdate = cy.stub().as('onUpdate');

        cy.fullMount(
            <CaseReviewBanner caseData={underReviewCase} onUpdate={onUpdate} />,
            mountOpts
        );

        cy.contains('button', 'Complete Review').click();
        cy.get('#review-outcome').type('Amended');
        cy.get('.MuiDialogActions-root').contains('button', 'Complete').click();
        cy.wait('@completeReview')
            .its('request.body')
            .should('deep.equal', { outcome: 'Amended' });
        cy.get('@onUpdate').should('have.been.called');
    });

    it('abandons a review and refreshes', () => {
        cy.intercept('POST', '**/cases/case-123/reviews/abandon', {
            statusCode: 200,
            body: { id: 'rev-1', status: 'ABANDONED' },
        }).as('abandonReview');
        const onUpdate = cy.stub().as('onUpdate');

        cy.fullMount(
            <CaseReviewBanner caseData={underReviewCase} onUpdate={onUpdate} />,
            mountOpts
        );

        cy.contains('button', 'Abandon Review').click();
        cy.contains('Abandon review').should('be.visible');
        cy.get('#review-outcome').type('Challenge withdrawn');
        cy.get('.MuiDialogActions-root').contains('button', 'Abandon').click();
        cy.wait('@abandonReview');
        cy.get('@onUpdate').should('have.been.called');
    });

    it('keeps the review open when closing fails', () => {
        cy.intercept('POST', '**/cases/case-123/reviews/complete', {
            statusCode: 500,
            body: { detail: 'boom' },
        }).as('completeFail');
        const onUpdate = cy.stub().as('onUpdate');

        cy.fullMount(
            <CaseReviewBanner caseData={underReviewCase} onUpdate={onUpdate} />,
            mountOpts
        );

        cy.contains('button', 'Complete Review').click();
        cy.get('#review-outcome').type('Amended');
        cy.get('.MuiDialogActions-root').contains('button', 'Complete').click();
        cy.wait('@completeFail');
        cy.get('@onUpdate').should('not.have.been.called');
    });
});
