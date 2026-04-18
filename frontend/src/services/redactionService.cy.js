import * as redactionService from './redactionService';
import apiClient from '@/api/apiClient';

describe('redactionService', () => {
    describe('bulkMarkByText', () => {
        beforeEach(() => {
            cy.stub(apiClient, 'post').as('apiPost');
        });

        it('calls the correct endpoint with ACCEPTED status', async () => {
            cy.get('@apiPost').resolves({ data: { updated: 3 } });

            const result = await redactionService.bulkMarkByText(
                'case-uuid-123',
                'John Doe',
                'PII',
                'ACCEPTED',
                null,
                'fake-token'
            );

            cy.get('@apiPost').should('have.been.calledOnce');
            cy.get('@apiPost').then((stub) => {
                const [url, body, config] = stub.args[0];
                expect(url).to.equal('cases/case-uuid-123/redactions/bulk-by-text/');
                expect(body.text).to.equal('John Doe');
                expect(body.redaction_type).to.equal('PII');
                expect(body.status).to.equal('ACCEPTED');
                expect(config.headers.Authorization).to.equal('Bearer fake-token');
            });
            expect(result.updated).to.equal(3);
        });

        it('calls the correct endpoint with REJECTED status and rejection reason', async () => {
            cy.get('@apiPost').resolves({ data: { updated: 2 } });

            await redactionService.bulkMarkByText(
                'case-uuid-456',
                'PC Smith',
                'OP_DATA',
                'REJECTED',
                'Not relevant to this case',
                'fake-token'
            );

            cy.get('@apiPost').then((stub) => {
                const [url, body] = stub.args[0];
                expect(url).to.equal('cases/case-uuid-456/redactions/bulk-by-text/');
                expect(body.redaction_type).to.equal('OP_DATA');
                expect(body.status).to.equal('REJECTED');
                expect(body.rejection_reason).to.equal('Not relevant to this case');
            });
        });

        it('throws a descriptive error when the request fails', async () => {
            cy.get('@apiPost').rejects(new Error('Network error'));

            try {
                await redactionService.bulkMarkByText(
                    'case-uuid-789', 'text', 'PII', 'ACCEPTED', null, 'token'
                );
                throw new Error('Expected error was not thrown');
            } catch (err) {
                expect(err.message).to.include('Failed to bulk mark redactions');
            }
        });
    });
});
