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
    font_family: 'georgia',
};

const defaultSettings = {
    header_text: '',
    footer_text: '',
    watermark_text: '',
    watermark_include_case_ref: false,
    page_numbers_enabled: false,
    font_family: 'arial',
};

describe('<DocumentExportSettingsCard />', () => {
    beforeEach(() => {
        cy.intercept('GET', '**/cases/settings/export', { body: defaultSettings }).as('getSettings');
    });

    it('renders the title and Configure button on the card', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('Document Export Settings').should('be.visible');
        cy.contains('button', 'Configure').should('be.visible');
    });

    it('opens the configure dialog when Configure is clicked', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.get('[role="dialog"]').should('be.visible');
        cy.get('[role="dialog"]').contains('Document Export Settings').should('be.visible');
    });

    it('renders all fields inside the dialog', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.get('textarea[aria-label="header text"]').should('be.visible');
        cy.get('textarea[aria-label="footer text"]').should('be.visible');
        cy.get('input[aria-label="watermark text"]').should('be.visible');
        cy.get('input[aria-label="include case reference in watermark"]').should('exist');
        cy.get('input[aria-label="show page numbers"]').should('exist');
        cy.get('#font-family-label').should('be.visible');
        cy.get('button').contains('Save').should('be.visible');
    });

    it('font select is populated from the GET response', () => {
        cy.intercept('GET', '**/cases/settings/export', { body: mockSettings }).as('getSettingsMockFont');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsMockFont');
        cy.get('[aria-labelledby="font-family-label"]').should('contain.text', 'Georgia');
    });

    it('populates fields from the GET response', () => {
        cy.intercept('GET', '**/cases/settings/export', { body: mockSettings }).as('getSettingsMock');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsMock');
        cy.get('textarea[aria-label="header text"]').should('have.value', 'OFFICIAL');
        cy.get('textarea[aria-label="footer text"]').should('have.value', 'Confidential');
        cy.get('input[aria-label="watermark text"]').should('have.value', 'SAR');
        cy.get('input[aria-label="include case reference in watermark"]').should('be.checked');
        cy.get('input[aria-label="show page numbers"]').should('be.checked');
    });

    it('calls PATCH with correct payload on save', () => {
        cy.intercept('PATCH', '**/cases/settings/export', { body: mockSettings }).as('patchSettings');
        cy.intercept('GET', '**/cases/settings/export', { body: defaultSettings }).as('getSettingsDefault');

        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsDefault');

        cy.get('textarea[aria-label="header text"]').type('OFFICIAL');
        cy.get('textarea[aria-label="footer text"]').type('Confidential');
        cy.get('button').contains('Save').click();

        cy.wait('@patchSettings').its('request.body').should('include', {
            header_text: 'OFFICIAL',
            footer_text: 'Confidential',
            font_family: 'arial',
        });
    });

    it('closes the dialog after successful save', () => {
        cy.intercept('PATCH', '**/cases/settings/export', { body: defaultSettings }).as('patchSettings');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.get('button').contains('Save').click();
        cy.wait('@patchSettings');
        cy.get('[role="dialog"]').should('not.exist');
    });

    it('disables "include case reference" switch when watermark text is empty', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.get('input[aria-label="include case reference in watermark"]').should('be.disabled');
    });

    it('enables "include case reference" switch when watermark text is entered', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.get('input[aria-label="include case reference in watermark"]').should('be.disabled');
        cy.get('input[aria-label="watermark text"]').type('DRAFT');
        cy.get('input[aria-label="include case reference in watermark"]').should('not.be.disabled');
    });

    it('resets fields to original values when Cancel is clicked after modifications', () => {
        cy.intercept('GET', '**/cases/settings/export', { body: mockSettings }).as('getSettingsMockCancel');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsMockCancel');

        cy.get('textarea[aria-label="header text"]').clear().type('MODIFIED VALUE');
        cy.get('textarea[aria-label="header text"]').should('have.value', 'MODIFIED VALUE');

        cy.contains('button', 'Cancel').click();
        cy.get('[role="dialog"]').should('not.exist');

        // Reopen — fields should show original values (reset by handleCloseConfigure from cached SWR data)
        cy.contains('button', 'Configure').click();
        cy.get('textarea[aria-label="header text"]').should('have.value', 'OFFICIAL');
    });

    it('shows error toast when save fails', () => {
        cy.intercept('PATCH', '**/cases/settings/export', { statusCode: 500, body: {} }).as('patchFail');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.contains('button', 'Save').click();
        cy.wait('@patchFail');
        cy.contains('Failed to update export settings. Please try again.').should('be.visible');
    });

    it('changes font family when a different option is selected', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.get('[aria-labelledby="font-family-label"]').click();
        cy.get('[role="listbox"]').contains('Times New Roman').click();
        cy.get('[aria-labelledby="font-family-label"]').should('contain.text', 'Times New Roman');
    });

    it('toggles the page numbers switch', () => {
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettings');
        cy.get('input[aria-label="show page numbers"]').should('not.be.checked');
        cy.get('input[aria-label="show page numbers"]').click({ force: true });
        cy.get('input[aria-label="show page numbers"]').should('be.checked');
    });

    it('toggles the case reference switch when watermark text is present', () => {
        cy.intercept('GET', '**/cases/settings/export', { body: mockSettings }).as('getSettingsWithWatermark');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsWithWatermark');
        cy.get('input[aria-label="include case reference in watermark"]').should('be.checked');
        cy.get('input[aria-label="include case reference in watermark"]').click({ force: true });
        cy.get('input[aria-label="include case reference in watermark"]').should('not.be.checked');
    });

    it('shows error message when GET fails', () => {
        cy.intercept('GET', '**/cases/settings/export', { statusCode: 500, body: {} }).as('getSettingsError');
        cy.fullMount(<TestWrapper><DocumentExportSettingsCard /></TestWrapper>, mountOpts);
        cy.contains('button', 'Configure').click();
        cy.wait('@getSettingsError');
        cy.contains('Failed to load export settings.').should('be.visible');
    });
});
