import React from 'react';
import { SWRConfig } from 'swr';
import { LLMPromptSettingsCard } from './LLMPromptSettingsCard';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

const defaultPrompt = 'You are a data protection specialist.';
const customPrompt = 'Custom prompt text here.';

const mockSettings = {
    system_prompt: customPrompt,
    default_system_prompt: defaultPrompt,
};

const defaultSettings = {
    system_prompt: defaultPrompt,
    default_system_prompt: defaultPrompt,
};

describe('<LLMPromptSettingsCard />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/llm-prompt-settings', { body: defaultSettings }).as('getSettings');
    });

    it('renders the title and Configure button', () => {
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('Contextual AI Prompt').should('be.visible');
        cy.contains('button', 'Configure').should('be.visible');
    });

    it('opens the dialog when Configure is clicked', () => {
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.get('[role="dialog"]').contains('Contextual AI Prompt Settings').should('be.visible');
    });

    it('renders the system prompt textarea inside the dialog', () => {
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.get('textarea[aria-label="system prompt"]').should('be.visible');
        cy.contains('button', 'Reset to default').should('be.visible');
        cy.contains('button', 'Save').should('be.visible');
    });

    it('populates the textarea from the GET response', () => {
        cy.intercept('GET', '**/llm-prompt-settings', { body: mockSettings }).as('getSettingsMock');
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsMock');
        cy.get('textarea[aria-label="system prompt"]').should('have.value', customPrompt);
    });

    it('resets textarea to default when Reset to default is clicked', () => {
        cy.intercept('GET', '**/llm-prompt-settings', { body: mockSettings }).as('getSettingsMock');
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsMock');
        cy.get('textarea[aria-label="system prompt"]').should('have.value', customPrompt);
        cy.contains('button', 'Reset to default').click();
        cy.get('textarea[aria-label="system prompt"]').should('have.value', defaultPrompt);
    });

    it('calls PATCH with the system prompt on save', () => {
        cy.intercept('PATCH', '**/llm-prompt-settings', { body: defaultSettings }).as('patchSettings');
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.get('textarea[aria-label="system prompt"]').clear().type('new prompt');
        cy.contains('button', 'Save').click();
        cy.wait('@patchSettings').its('request.body').should('deep.equal', {
            system_prompt: 'new prompt',
        });
    });

    it('closes the dialog after a successful save', () => {
        cy.intercept('PATCH', '**/llm-prompt-settings', { body: defaultSettings }).as('patchSettings');
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.contains('button', 'Save').click();
        cy.wait('@patchSettings');
        cy.get('[role="dialog"]').should('not.exist');
    });

    it('resets textarea to original value when Cancel is clicked', () => {
        cy.intercept('GET', '**/llm-prompt-settings', { body: mockSettings }).as('getSettingsMock');
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsMock');
        cy.get('textarea[aria-label="system prompt"]').clear().type('modified');
        cy.contains('button', 'Cancel').click();
        cy.get('[role="dialog"]').should('not.exist');
        cy.contains('button', 'Configure').click();
        cy.get('textarea[aria-label="system prompt"]').should('have.value', customPrompt);
    });

    it('shows error message when GET fails', () => {
        cy.intercept('GET', '**/llm-prompt-settings', { statusCode: 500, body: {} }).as('getSettingsError');
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsError');
        cy.contains('Failed to load prompt settings.').should('be.visible');
    });

    it('shows error toast when save fails', () => {
        cy.intercept('PATCH', '**/llm-prompt-settings', { statusCode: 500, body: {} }).as('patchFail');
        cy.fullMount(<TestWrapper><LLMPromptSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.contains('button', 'Save').click();
        cy.wait('@patchFail');
        cy.contains('Failed to update LLM prompt settings.').should('be.visible');
    });
});
