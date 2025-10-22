import React from 'react';
import { DocumentViewer } from '@/components/DocumentViewer';

describe('<DocumentViewer />', () => {
    const text = 'This text contains PII, some operational data, and information about the data subject. It also has a rejected suggestion.';

    const redactions = [
        // Accepted PII redaction
        { id: 'redaction-1', start_char: 19, end_char: 22, text: 'PII', redaction_type: 'PII', is_accepted: true, is_suggestion: true },
        // Accepted OP_DATA redaction
        { id: 'redaction-2', start_char: 29, end_char: 45, text: 'operational data', redaction_type: 'OP_DATA', is_accepted: true, is_suggestion: true },
        // Pending suggestion (DS_INFO)
        { id: 'redaction-3', start_char: 73, end_char: 85, text: 'data subject', redaction_type: 'DS_INFO', is_accepted: false, is_suggestion: true, justification: null },
        // Rejected suggestion
        { id: 'redaction-4', start_char: 101, end_char: 120, text: 'rejected suggestion', redaction_type: 'PII', is_accepted: false, is_suggestion: true, justification: 'Not relevant' },
    ];

    beforeEach(() => {
        cy.viewport(1200, 800);
    });

    context('Review Mode (Default)', () => {
        let onHighlightClick;
        let onTextSelect;

        beforeEach(() => {
            onHighlightClick = cy.spy().as('onHighlightClick');
            onTextSelect = cy.spy().as('onTextSelect');
            cy.mount(
                <DocumentViewer
                    text={text}
                    redactions={redactions}
                    onHighlightClick={onHighlightClick}
                    onTextSelect={onTextSelect}
                />
            );
        });

        it('returns null / renders nothing when no text prop is provided', () => {
        cy.mount(<DocumentViewer redactions={[]} />);
        cy.get('span').should('not.exist');
    });

        it('renders accepted, suggested, and rejected redactions with correct colors', () => {
            // Accepted PII (Green)
            cy.contains('span', 'PII')
                .should('be.visible')
                .and('have.css', 'background-color', 'rgba(46, 204, 113, 0.7)');

            // Accepted OP_DATA (Blue)
            cy.contains('span', 'operational data')
                .should('be.visible')
                .and('have.css', 'background-color', 'rgba(0, 221, 255, 0.7)');

            // Pending Suggestion (Yellow)
            cy.contains('span', 'data subject')
                .should('be.visible')
                .and('have.css', 'background-color', 'rgba(255, 214, 10, 0.4)');

            // Rejected Suggestion (Grey)
            cy.contains('span', 'rejected suggestion')
                .should('be.visible')
                .and('have.css', 'background-color', 'rgba(189, 195, 199, 0.5)');
        });

        it('calls onHighlightClick with the correct ID when a redaction is clicked', () => {
            cy.contains('span', 'operational data').click();
            cy.get('@onHighlightClick').should('have.been.calledOnceWith', 'redaction-2');
        });

        it('calls onTextSelect with correct details when text is selected', () => {
            cy.get('div').contains('This text contains').as('textNode');

            cy.get('@textNode').then($el => {
                const element = $el[0];
                const textNode = element.firstChild;
                const range = document.createRange();
                range.setStart(textNode, 5); // "text"
                range.setEnd(textNode, 9);
                window.getSelection().removeAllRanges();
                window.getSelection().addRange(range);
            }).trigger('mouseup');

            cy.get('@onTextSelect').should('have.been.calledOnce');
            cy.get('@onTextSelect').should((spy) => {
                const [selection] = spy.getCall(0).args;
                expect(selection.text).to.equal('text');
                expect(selection.start_char).to.equal(5);
                expect(selection.end_char).to.equal(9);
            });
        });

        it('shows a border on hover when hoveredSuggestionId is passed', () => {
            cy.mount(
                <DocumentViewer
                    text={text}
                    redactions={redactions}
                    hoveredSuggestionId="redaction-3"
                />
            );

            cy.contains('span', 'data subject')
                .should('have.css', 'border', '1px solid rgb(255, 165, 0)'); // PENDING border color
        });

        it('renders a pending redaction for new selections', () => {
            const pendingRedaction = {
                start_char: 0,
                end_char: 4,
                text: 'This',
            };
            cy.mount(
                <DocumentViewer
                    text={text}
                    redactions={redactions}
                    pendingRedaction={pendingRedaction}
                />
            );

            cy.contains('span', 'This')
                .should('have.css', 'background-color', 'rgba(255, 214, 10, 0.6)');
        });
    });

    context('Final Mode', () => {
        it('renders accepted redactions as black boxes and hides suggestions', () => {
            cy.mount(
                <DocumentViewer
                    text={text}
                    redactions={redactions.filter(r => r.is_accepted)}
                    viewMode="final"
                />
            );

            cy.contains('span', 'PII')
                .should('be.visible')
                .and('have.css', 'background-color', 'rgb(0, 0, 0)')
                .and('have.css', 'color', 'rgb(0, 0, 0)');

            cy.contains('span', 'operational data')
                .should('be.visible')
                .and('have.css', 'background-color', 'rgb(0, 0, 0)')
                .and('have.css', 'color', 'rgb(0, 0, 0)');

            cy.contains('span', 'data subject').should('not.exist');
            cy.contains('span', 'rejected suggestion').should('not.exist');
        });
    });

    context('Color-Coded Mode', () => {
        it('renders accepted redactions with solid colors and hides suggestions', () => {
            cy.mount(
                <DocumentViewer
                    text={text}
                    redactions={redactions.filter(r => r.is_accepted)}
                    viewMode="color-coded"
                />
            );

            // Accepted PII
            cy.contains('span', 'PII')
                .should('be.visible')
                .and('have.css', 'background-color', 'rgba(46, 204, 113, 0.7)');

            // Accepted OP_DATA
            cy.contains('span', 'operational data')
                .should('be.visible')
                .and('have.css', 'background-color', 'rgba(0, 221, 255, 0.7)');

            // Suggestions and rejected redactions should not be present
            cy.contains('span', 'data subject').should('not.exist');
            cy.contains('span', 'rejected suggestion').should('not.exist');
        });
    });
});