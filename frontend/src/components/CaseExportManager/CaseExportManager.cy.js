import React, { useState } from 'react';
import { CaseExportManager } from './CaseExportManager';

describe('<CaseExportManager />', () => {
    const CaseDataWrapper = ({ initialData }) => {
        const [caseData, setCaseData] = useState(initialData);
        React.useEffect(() => {
            window.updateCaseData = setCaseData;
            return () => {
                delete window.updateCaseData;
            };
        }, []);

        return <CaseExportManager caseData={caseData} onUpdate={() => {}} />;
    };
    const baseCaseData = {
        id: 'case-123',
        export_status: 'NONE',
        export_file: null,
    };

    const mountOptions = {
        mockSession: {
            access_token: 'fake-token',
            status: 'authenticated',
        },
    };

    context('when status is NONE', () => {
        it('renders the generate button and calls the API on click', () => {
            const onUpdateSpy = cy.spy().as('onUpdateSpy');
            cy.intercept('POST', `**/cases/${baseCaseData.id}/export`, {
                statusCode: 200,
                body: { case_id: baseCaseData.id, export_status: 'PROCESSING' },
            }).as('postExport');
            const testCaseData = { ...baseCaseData, documents: [{ id: 'doc-1', status: 'Completed' }] };
            cy.fullMount(
                <CaseExportManager caseData={testCaseData} onUpdate={onUpdateSpy} />,
                mountOptions
            );

            cy.contains('button', 'Generate Disclosure Package').should('be.visible').and('be.enabled');
            cy.contains('button', 'Generate Disclosure Package').click();
            cy.contains('button', 'Generate Disclosure Package').should('be.disabled');
            cy.wait('@postExport');
            cy.get('@onUpdateSpy').should('have.been.calledOnce');
        });

        it('shows an error toast if the API call fails', () => {
            cy.intercept('POST', `**/cases/${baseCaseData.id}/export`, { statusCode: 500 }).as('postExportError');
            const testCaseData = { ...baseCaseData, documents: [{ id: 'doc-1', status: 'Completed' }] };
            cy.fullMount(
                <CaseExportManager caseData={testCaseData} onUpdate={() => {}} />,
                mountOptions
            );

            cy.contains('button', 'Generate Disclosure Package').click();
            cy.wait('@postExportError');
            cy.contains('Failed to start export process.').should('be.visible');
            cy.contains('button', 'Generate Disclosure Package').should('be.enabled');
        });
    });

    context('when status is PROCESSING', () => {
        it('renders the disabled processing button', () => {
            const processingCase = { ...baseCaseData, export_status: 'PROCESSING' };
            cy.fullMount(<CaseExportManager caseData={processingCase} />, mountOptions);

            cy.contains('button', 'Generating Package...').should('be.disabled');
            cy.get('[role="progressbar"]').should('be.visible');
        });
    });

    context('when status is COMPLETED', () => {
        it('renders a download link', () => {
            const completedCase = {
                ...baseCaseData,
                export_status: 'COMPLETED',
                export_file: '/downloads/case-123.zip',
            };
            cy.fullMount(<CaseExportManager caseData={completedCase} />, mountOptions);

            cy.contains('a', 'Download Package')
                .should('be.visible')
                .and('have.attr', 'href', completedCase.export_file)
                .and('have.attr', 'download');
        });
    });

    context('when status is ERROR', () => {
        it('renders a retry button that re-triggers the export', () => {
            cy.intercept('POST', `**/cases/${baseCaseData.id}/export`).as('postExport');
            const errorCase = { ...baseCaseData, export_status: 'ERROR', documents: [{ id: 'doc-1', status: 'Completed' }] };
            cy.fullMount(<CaseExportManager caseData={errorCase} />, mountOptions);

            cy.contains('button', 'Retry Export').should('be.visible').click();
            cy.wait('@postExport');
        });
    });

    context('State Transitions and Toasts', () => {
        it('shows a success toast when status changes from PROCESSING to COMPLETED', () => {
            const processingCase = { ...baseCaseData, export_status: 'PROCESSING' };
            const completedCase = { ...baseCaseData, export_status: 'COMPLETED', export_file: '/downloads/case-123.zip' };

            cy.fullMount(<CaseDataWrapper initialData={processingCase} />, mountOptions);

            cy.window().invoke('updateCaseData', completedCase);
            cy.contains('Export package is ready for download.').should('be.visible');
        });

        it('shows an error toast when status changes from PROCESSING to ERROR', () => {
            const processingCase = { ...baseCaseData, export_status: 'PROCESSING' };
            const errorCase = { ...baseCaseData, export_status: 'ERROR' };

            cy.fullMount(<CaseDataWrapper initialData={processingCase} />, mountOptions);
            cy.window().invoke('updateCaseData', errorCase);
            cy.contains('There was an error generating the export.').should('be.visible');
        });
    });
});