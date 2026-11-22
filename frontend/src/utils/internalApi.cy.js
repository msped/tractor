import { internalApiHeaders } from './internalApi';

describe('internalApiHeaders', () => {
    it('forwards https when the public site is served over HTTPS', () => {
        expect(internalApiHeaders('https://tractor.example.com')).to.deep.equal({
            'X-Forwarded-Proto': 'https',
        });
    });

    it('adds nothing for an HTTP-only deployment', () => {
        expect(internalApiHeaders('http://localhost:3000')).to.deep.equal({});
    });

    it('adds nothing when the public URL is unset', () => {
        expect(internalApiHeaders('')).to.deep.equal({});
        expect(internalApiHeaders(undefined)).to.deep.equal({});
    });
});
