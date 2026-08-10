import {
    extractApiError,
    extractServerMessage,
    resolveErrorMessage,
    throwApiError,
} from './apiError';

const axiosError = (status, data) => ({ response: { status, data } });

describe('extractServerMessage', () => {
    it('reads DRF field names in priority order', () => {
        expect(
            extractServerMessage(axiosError(400, { detail: 'A', error: 'B' }))
        ).to.equal('A');
        expect(
            extractServerMessage(
                axiosError(400, { non_field_errors: ['B'], error: 'C' })
            )
        ).to.equal('B');
        expect(
            extractServerMessage(axiosError(400, { name: ['C'], error: 'D' }))
        ).to.equal('C');
        expect(extractServerMessage(axiosError(400, { error: 'D' }))).to.equal(
            'D'
        );
    });

    it('returns null when the server said nothing usable', () => {
        expect(extractServerMessage(axiosError(500, {}))).to.equal(null);
        expect(extractServerMessage(axiosError(502, '<html>502</html>'))).to.equal(
            null
        );
        // A bare network failure has no response at all.
        expect(extractServerMessage(new Error('Network Error'))).to.equal(null);
    });
});

describe('extractApiError', () => {
    it('falls back only when there is no server message', () => {
        expect(extractApiError(axiosError(400, { detail: 'Real' }), 'Fb')).to.equal(
            'Real'
        );
        expect(extractApiError(axiosError(500, {}), 'Fb')).to.equal('Fb');
    });
});

describe('throwApiError', () => {
    it('marks a server-provided message and carries the status', () => {
        try {
            throwApiError(axiosError(409, { detail: 'Case is locked.' }), 'Fb');
            throw new Error('should have thrown');
        } catch (err) {
            expect(err.message).to.equal('Case is locked.');
            expect(err.status).to.equal(409);
            expect(err.isServerMessage).to.equal(true);
        }
    });

    it('marks a fallback message as not server-provided', () => {
        try {
            throwApiError(new Error('Network Error'), 'Fb');
            throw new Error('should have thrown');
        } catch (err) {
            expect(err.message).to.equal('Fb');
            expect(err.status).to.equal(undefined);
            expect(err.isServerMessage).to.equal(false);
        }
    });
});

describe('resolveErrorMessage', () => {
    beforeEach(() => {
        cy.spy(console, 'error').as('consoleError');
    });

    const serviceError = (message, status, isServerMessage) =>
        Object.assign(new Error(message), { status, isServerMessage });

    it('shows the reason a 4xx gave, without logging it', () => {
        const message = resolveErrorMessage(
            serviceError('Case is already exported.', 409, true),
            'Failed to export. Please try again.'
        );
        expect(message).to.equal('Case is already exported.');
        // An expected client error is not console noise.
        cy.get('@consoleError').should('not.have.been.called');
    });

    it('shows a 5xx reason and still logs it', () => {
        // Our DRF handler puts the support reference in `detail`, so hiding it
        // behind the fallback would throw away the only actionable detail.
        const message = resolveErrorMessage(
            serviceError('Server error. Quote reference ab12cd34.', 500, true),
            'Failed to save. Please try again.'
        );
        expect(message).to.equal('Server error. Quote reference ab12cd34.');
        cy.get('@consoleError').should('have.been.calledOnce');
    });

    it('falls back and logs when the server explained nothing', () => {
        const message = resolveErrorMessage(
            serviceError('Failed to save. Please try again.', 500, false),
            'Failed to save. Please try again.'
        );
        expect(message).to.equal('Failed to save. Please try again.');
        cy.get('@consoleError').should('have.been.calledOnce');
    });

    it('falls back and logs for a network failure with no status', () => {
        const message = resolveErrorMessage(
            serviceError('Failed to load. Please try again.', undefined, false),
            'Failed to load. Please try again.'
        );
        expect(message).to.equal('Failed to load. Please try again.');
        cy.get('@consoleError').should('have.been.calledOnce');
    });

    it('tolerates a non-service error', () => {
        expect(resolveErrorMessage(new Error('raw'), 'Fb')).to.equal('Fb');
        expect(resolveErrorMessage(undefined, 'Fb')).to.equal('Fb');
    });
});
