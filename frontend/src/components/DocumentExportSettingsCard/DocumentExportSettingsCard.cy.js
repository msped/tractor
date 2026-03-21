import React from 'react';
import { SWRConfig } from 'swr';
import { DocumentExportSettingsCard } from './DocumentExportSettingsCard';

const mountOpts = { mockSession: { access_token: 'fake-token', status: 'authenticated' } };

const TestWrapper = ({ children }) => (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        {children}
    </SWRConfig>
);

const mockSettings = {
    header_text: 'OFFICIAL',
    footer_text: 'Confidential',
    watermark_text: 'SAR',
    watermark_include_case_ref: true,
    page_numbers_enabled: true,
};

const defaultSettings = {
    header_text: '',
    footer_text: '',
    watermark_text: '',
    watermark_include_case_ref: false,
    page_numbers_enabled: false,
};

describe('<DocumentExportSettingsCard />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/cases/settings/export', { body: defaultSettings }).as('getSettings');
    });

    it('renders the title and all fields', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.contains('Document Export Settings').should('be.visible');
        cy.get('input[aria-label="header text"]').should('be.visible');
        cy.get('input[aria-label="footer text"]').should('be.visible');
        cy.get('input[aria-label="watermark text"]').should('be.visible');
        cy.get('input[aria-label="include case reference in watermark"]').should('exist');
        cy.get('input[aria-label="show page numbers"]').should('exist');
        cy.get('button').contains('Save').should('be.visible');
    });

    it('populates fields from the GET response', () => {
        cy.intercept('GET', '**/cases/settings/export', { body: mockSettings }).as('getSettingsMock');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettingsMock');
        cy.get('input[aria-label="header text"]').should('have.value', 'OFFICIAL');
        cy.get('input[aria-label="footer text"]').should('have.value', 'Confidential');
        cy.get('input[aria-label="watermark text"]').should('have.value', 'SAR');
        cy.get('input[aria-label="include case reference in watermark"]').should('be.checked');
        cy.get('input[aria-label="show page numbers"]').should('be.checked');
    });

    it('calls PATCH with correct payload on save', () => {
        cy.intercept('PATCH', '**/cases/settings/export', { body: mockSettings }).as('patchSettings');
        cy.intercept('GET', '**/cases/settings/export', { body: defaultSettings }).as('getSettingsDefault');

        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettingsDefault');

        cy.get('input[aria-label="header text"]').type('OFFICIAL');
        cy.get('input[aria-label="footer text"]').type('Confidential');
        cy.get('button').contains('Save').click();

        cy.wait('@patchSettings').its('request.body').should('include', {
            header_text: 'OFFICIAL',
            footer_text: 'Confidential',
        });
    });

    it('disables "include case reference" switch when watermark text is empty', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.get('input[aria-label="include case reference in watermark"]').should('be.disabled');
    });

    it('enables "include case reference" switch when watermark text is entered', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettings');
        cy.get('input[aria-label="include case reference in watermark"]').should('be.disabled');
        cy.get('input[aria-label="watermark text"]').type('DRAFT');
        cy.get('input[aria-label="include case reference in watermark"]').should('not.be.disabled');
    });

    it('shows error message when GET fails', () => {
        cy.intercept('GET', '**/cases/settings/export', { statusCode: 500, body: {} }).as('getSettingsError');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.wait('@getSettingsError');
        cy.contains('Failed to load export settings.').should('be.visible');
    });
});
