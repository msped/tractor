import { withheldSpans, disclosedRanges } from './withheldSpans';

const DS = 'DS_INFO';
const OP = 'OP_DATA';
const PII = 'PII';

// ── helpers ──────────────────────────────────────────────────────────────────

function span(id, start, end, type = OP) {
    return { id, start_char: start, end_char: end, redaction_type: type, text: `text_${id}` };
}

function offsets(pieces) {
    return pieces.map(p => [p.start_char, p.end_char]);
}

// ── disclosedRanges ──────────────────────────────────────────────────────────

describe('disclosedRanges', () => {
    it('collects only DS_INFO spans', () => {
        const spans = [span('a', 0, 5, OP), span('b', 10, 15, DS), span('c', 20, 25, PII)];
        expect(disclosedRanges(spans)).to.deep.equal([[10, 15]]);
    });

    it('merges overlapping DS_INFO claims', () => {
        const spans = [span('a', 10, 20, DS), span('b', 15, 25, DS)];
        expect(disclosedRanges(spans)).to.deep.equal([[10, 25]]);
    });

    it('merges abutting DS_INFO claims', () => {
        const spans = [span('a', 10, 20, DS), span('b', 20, 30, DS)];
        expect(disclosedRanges(spans)).to.deep.equal([[10, 30]]);
    });

    it('keeps disjoint claims separate and sorted', () => {
        const spans = [span('a', 30, 40, DS), span('b', 10, 20, DS)];
        expect(disclosedRanges(spans)).to.deep.equal([[10, 20], [30, 40]]);
    });

    it('is empty without DS_INFO', () => {
        expect(disclosedRanges([span('a', 0, 5, OP)])).to.deep.equal([]);
    });
});

// ── withheldSpans ────────────────────────────────────────────────────────────

describe('withheldSpans', () => {
    it('never withholds DS_INFO itself', () => {
        expect(withheldSpans([span('a', 0, 5, DS)])).to.deep.equal([]);
    });

    it('leaves a span that does not overlap a claim untouched', () => {
        const op = span('a', 0, 5, OP);
        expect(withheldSpans([op, span('b', 10, 15, DS)])).to.deep.equal([op]);
    });

    it('passes spans through unchanged when there is no DS_INFO', () => {
        const a = span('a', 10, 15, OP);
        const b = span('b', 0, 5, PII);
        expect(withheldSpans([a, b])).to.deep.equal([b, a]);
    });

    it('splits a span claimed through the middle', () => {
        // 'JONES, Michael #0712345' with 'Michael' disclosed inside it.
        const pieces = withheldSpans([span('op', 9, 32, OP), span('ds', 16, 23, DS)]);
        expect(offsets(pieces)).to.deep.equal([[9, 16], [23, 32]]);
        expect(pieces.every(p => p.redaction_type === OP)).to.be.true;
    });

    it('keeps the original id on each piece', () => {
        const pieces = withheldSpans([span('op', 9, 32, OP), span('ds', 16, 23, DS)]);
        expect(pieces.map(p => p.id)).to.deep.equal(['op', 'op']);
    });

    it('trims the front when the claim is at the start', () => {
        const pieces = withheldSpans([span('op', 9, 32, OP), span('ds', 9, 16, DS)]);
        expect(offsets(pieces)).to.deep.equal([[16, 32]]);
    });

    it('trims the back when the claim is at the end', () => {
        const pieces = withheldSpans([span('op', 9, 32, OP), span('ds', 23, 32, DS)]);
        expect(offsets(pieces)).to.deep.equal([[9, 23]]);
    });

    it('removes a span the claim covers entirely', () => {
        expect(withheldSpans([span('op', 9, 32, OP), span('ds', 9, 32, DS)])).to.deep.equal([]);
    });

    it('removes a span narrower than the claim', () => {
        expect(withheldSpans([span('op', 12, 20, OP), span('ds', 9, 32, DS)])).to.deep.equal([]);
    });

    it('splits into three around two interior claims', () => {
        const pieces = withheldSpans([
            span('op', 0, 40, OP),
            span('d1', 10, 15, DS),
            span('d2', 25, 30, DS),
        ]);
        expect(offsets(pieces)).to.deep.equal([[0, 10], [15, 25], [30, 40]]);
    });

    it('cuts every span a single claim overlaps', () => {
        const pieces = withheldSpans([
            span('op', 0, 20, OP),
            span('pii', 10, 30, PII),
            span('ds', 12, 18, DS),
        ]);
        expect(offsets(pieces)).to.deep.equal([[0, 12], [10, 12], [18, 20], [18, 30]]);
    });

    it('returns pieces sorted by position', () => {
        const pieces = withheldSpans([
            span('a', 30, 40, OP),
            span('b', 0, 10, PII),
            span('ds', 5, 7, DS),
        ]);
        expect(offsets(pieces)).to.deep.equal([[0, 5], [7, 10], [30, 40]]);
    });
});
