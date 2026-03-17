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

    // baseCaseData has a final status so the export flow is visible by default
    const baseCaseData = {
        id: 'case-123',
        status: 'COMPLETED',
        export_status: 'NONE',
        export_file: null,
    };

    const mountOptions = {
        mockSession: {
            access_token: 'fake-token',
            status: 'authenticated',
        },
    };

    context('when case is not locked (OPEN/IN_PROGRESS/UNDER_REVIEW)', () => {
        it('shows a disabled Complete Case button when documents are incomplete', () => {
            const testCaseData = {
                ...baseCaseData,
                status: 'OPEN',
                documents: [{ id: 'doc-1', status: 'In Review' }],
            };
            cy.fullMount(<CaseExportManager caseData={testCaseData} onUpdate={() => {}} />, mountOptions);

            cy.contains('button', 'Complete Case').should('be.disabled');
        });

        it('shows an enabled Complete Case button when all documents are completed', () => {
            const testCaseData = {
                ...baseCaseData,
                status: 'OPEN',
                documents: [{ id: 'doc-1', status: 'Completed' }],
            };
            cy.fullMount(<CaseExportManager caseData={testCaseData} onUpdate={() => {}} />, mountOptions);

            cy.contains('button', 'Complete Case').should('be.enabled');
        });

        it('calls updateCase with COMPLETED and onUpdate when Complete Case is clicked', () => {
            const onUpdateSpy = cy.spy().as('onUpdateSpy');
            cy.intercept('PATCH', `**/cases/${baseCaseData.id}`, {
                statusCode: 200,
                body: { status: 'COMPLETED' },
            }).as('patchCase');

            const testCaseData = {
                ...baseCaseData,
                status: 'OPEN',
                documents: [{ id: 'doc-1', status: 'Completed' }],
            };
            cy.fullMount(<CaseExportManager caseData={testCaseData} onUpdate={onUpdateSpy} />, mountOptions);

            cy.contains('button', 'Complete Case').click();
            cy.wait('@patchCase');
            cy.get('@onUpdateSpy').should('have.been.calledOnce');
        });

        it('shows Mark as Closed and Mark as Withdrawn in the dropdown', () => {
            const testCaseData = {
                ...baseCaseData,
                status: 'IN_PROGRESS',
                documents: [{ id: 'doc-1', status: 'Completed' }],
            };
            cy.fullMount(<CaseExportManager caseData={testCaseData} onUpdate={() => {}} />, mountOptions);

            cy.get('[data-testid="ArrowDropDownIcon"]').closest('button').click();
            cy.contains('li', 'Mark as Closed').should('be.visible');
            cy.contains('li', 'Mark as Withdrawn').should('be.visible');
        });

        it('calls updateCase with CLOSED when Mark as Closed is clicked', () => {
            const onUpdateSpy = cy.spy().as('onUpdateSpy');
            cy.intercept('PATCH', `**/cases/${baseCaseData.id}`, {
                statusCode: 200,
                body: { status: 'CLOSED' },
            }).as('patchCase');

            const testCaseData = {
                ...baseCaseData,
                status: 'OPEN',
                documents: [{ id: 'doc-1', status: 'Completed' }],
            };
            cy.fullMount(<CaseExportManager caseData={testCaseData} onUpdate={onUpdateSpy} />, mountOptions);

            cy.get('[data-testid="ArrowDropDownIcon"]').closest('button').click();
            cy.contains('li', 'Mark as Closed').click();
            cy.wait('@patchCase');
            cy.get('@onUpdateSpy').should('have.been.calledOnce');
        });
    });

    context('when case is locked and export status is NONE', () => {
        it('calls the API and onUpdate when Generate Disclosure Package is clicked', () => {
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

            cy.contains('button', 'Generate Disclosure Package').should('be.visible').and('be.enabled').click();
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

    context('when case is locked and export status is PROCESSING', () => {
        it('renders the disabled processing button', () => {
            const processingCase = { ...baseCaseData, export_status: 'PROCESSING' };
            cy.fullMount(<CaseExportManager caseData={processingCase} />, mountOptions);

            cy.contains('button', 'Generating Package...').should('be.disabled');
            cy.get('[role="progressbar"]').should('be.visible');
        });
    });

    context('when case is locked and export status is COMPLETED', () => {
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

    context('when case is locked and export status is ERROR', () => {
        it('renders a retry button that re-triggers the export directly', () => {
            cy.intercept('POST', `**/cases/${baseCaseData.id}/export`, { statusCode: 200, body: {} }).as('postExport');
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
