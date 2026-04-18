import React from 'react';
import { SWRConfig } from 'swr';
import { CustomRecognizersCard } from './CustomRecognizersCard';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

const mockRecognizers = [
    {
        id: 'uuid-1',
        name: 'Crime Ref Pattern',
        description: 'Matches local crime references',
        entity_type: 'OPERATIONAL',
        is_active: true,
        patterns: [{ id: 1, name: 'p1', regex: '\\d{2}/\\d{4}/\\d{2}', score: 0.9 }],
        deny_list: [],
    },
    {
        id: 'uuid-2',
        name: 'Known Names',
        description: '',
        entity_type: 'THIRD_PARTY',
        is_active: false,
        patterns: [],
        deny_list: [{ id: 2, value: 'John Smith' }],
    },
];

describe('<CustomRecognizersCard />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/model-management/custom-recognizers', { body: mockRecognizers }).as('getRecognizers');
        cy.intercept('POST', '**/model-management/regex/validate', { body: { valid: true, matches: [] } });
    });

    it('renders the card title and description', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('Custom Recognizers').should('be.visible');
        cy.contains('Domain-specific regex patterns').should('be.visible');
    });

    it('shows recognizer count on the card', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('2 recognizers').should('be.visible');
        cy.contains('1 active').should('be.visible');
    });

    it('opens the manage dialog when Manage is clicked', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.contains('Crime Ref Pattern').should('be.visible');
        cy.contains('Known Names').should('be.visible');
    });

    it('shows entity type chips in the table', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.contains('Operational Data').should('be.visible');
        cy.contains('Third-Party PII').should('be.visible');
    });

    it('shows pattern and deny-list counts in the table', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.contains('1 pattern').should('be.visible');
        cy.contains('1 term').should('be.visible');
    });

    it('opens the add form when Add recognizer is clicked', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Add recognizer').click();
        cy.contains('Add Recognizer').should('be.visible');
        cy.get('[aria-label="recognizer name"]').should('be.visible');
    });

    it('add form allows adding and removing pattern rows', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Add recognizer').click();

        // Initially one pattern row
        cy.get('[aria-label="pattern regex 1"]').should('be.visible');

        // Add another pattern row
        cy.contains('button', 'Add pattern').click();
        cy.get('[aria-label="pattern regex 2"]').should('be.visible');

        // Remove the second row
        cy.get('[aria-label="remove pattern 2"]').click();
        cy.get('[aria-label="pattern regex 2"]').should('not.exist');
    });

    it('switching to deny list mode shows deny list fields', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Add recognizer').click();

        // Change recognizer type to deny list
        cy.get('[aria-label="recognizer type"]').parent().click();
        cy.get('[data-value="deny_list"]').click();

        cy.get('[aria-label="deny list value 1"]').should('be.visible');
        cy.get('[aria-label="pattern regex 1"]').should('not.exist');
    });

    it('submit button is disabled when name is empty', () => {
        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Add recognizer').click();

        cy.get('[aria-label="recognizer name"]').should('have.value', '');
        cy.contains('button', 'Save').should('be.disabled');
    });

    it('creates a recognizer and closes the form', () => {
        cy.intercept('POST', '**/model-management/custom-recognizers', { statusCode: 201, body: { id: 'uuid-3', name: 'New Rec', entity_type: 'THIRD_PARTY', is_active: true, patterns: [], deny_list: [] } }).as('createRecognizer');

        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.contains('button', 'Add recognizer').click();

        cy.get('[aria-label="recognizer name"]').type('New Rec');
        cy.get('[aria-label="pattern regex 1"]').type('\\d+');
        cy.contains('button', 'Save').click();

        cy.wait('@createRecognizer');
        cy.contains('Add Recognizer').should('not.exist');
    });

    it('deletes a recognizer after confirmation', () => {
        cy.intercept('DELETE', '**/model-management/custom-recognizers/uuid-1', { statusCode: 204 }).as('deleteRecognizer');

        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.get('[aria-label="delete Crime Ref Pattern"]').click();

        // Confirm dialog should appear
        cy.contains('Delete Custom Recognizer').should('be.visible');
        cy.contains('button', 'Delete').click();

        cy.wait('@deleteRecognizer');
    });

    it('toggling a recognizer calls update endpoint', () => {
        cy.intercept('PATCH', '**/model-management/custom-recognizers/uuid-1', { body: { ...mockRecognizers[0], is_active: false } }).as('toggleRecognizer');

        cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
        cy.wait('@getRecognizers');
        cy.contains('button', 'Manage').click();
        cy.get('[aria-label="toggle Crime Ref Pattern"]').click();

        cy.wait('@toggleRecognizer');
    });

    // --- Regex tester (#100) ---
    describe('Regex tester', () => {
        beforeEach(() => {
            cy.intercept('POST', '**/model-management/regex/validate', (req) => {
                const { pattern, sample_text } = req.body;
                try {
                    const re = new RegExp(pattern, 'g');
                    const matches = [];
                    let m;
                    while ((m = re.exec(sample_text)) !== null) {
                        matches.push({ start: m.index, end: m.index + m[0].length, text: m[0] });
                    }
                    req.reply({ valid: true, matches });
                } catch (e) {
                    req.reply({ statusCode: 400, body: { valid: false, error: e.message } });
                }
            }).as('validateRegex');
        });

        it('shows regex tester when a pattern is entered', () => {
            cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
            cy.wait('@getRecognizers');
            cy.contains('button', 'Manage').click();
            cy.contains('button', 'Add recognizer').click();

            cy.get('[aria-label="pattern regex 1"]').type('\\d+');
            cy.contains('Regex tester').should('be.visible');
        });

        it('highlights matches in sample text after debounce', () => {
            cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
            cy.wait('@getRecognizers');
            cy.contains('button', 'Manage').click();
            cy.contains('button', 'Add recognizer').click();

            cy.get('[aria-label="pattern regex 1"]').type('\\d+');
            cy.get('[aria-label="sample text for regex tester"]').type('abc 123 def 456');

            cy.wait('@validateRegex');
            cy.get('mark').should('have.length.gte', 1);
        });

        it('shows error message for invalid regex', () => {
            cy.intercept('POST', '**/model-management/regex/validate', {
                statusCode: 400,
                body: { valid: false, error: 'unterminated character class' },
            }).as('validateInvalid');

            cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
            cy.wait('@getRecognizers');
            cy.contains('button', 'Manage').click();
            cy.contains('button', 'Add recognizer').click();

            cy.get('[aria-label="pattern regex 1"]').type('[invalid');
            cy.get('[aria-label="sample text for regex tester"]').type('test');

            cy.wait('@validateInvalid');
            cy.contains('unterminated character class').should('be.visible');
        });

        it('shows no matches message when pattern has no matches', () => {
            cy.fullMount(<TestWrapper><CustomRecognizersCard /></TestWrapper>, mountOpts);
            cy.wait('@getRecognizers');
            cy.contains('button', 'Manage').click();
            cy.contains('button', 'Add recognizer').click();

            cy.get('[aria-label="pattern regex 1"]').type('\\d+');
            cy.get('[aria-label="sample text for regex tester"]').type('no digits here');

            cy.wait('@validateRegex');
            cy.contains('No matches').should('be.visible');
        });
    });
});
