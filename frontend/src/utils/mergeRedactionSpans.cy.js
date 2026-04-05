import { mergeAdjacentSpans, groupByTextAndType } from './mergeRedactionSpans';

const OPERATIONAL = 'OPERATIONAL';
const THIRD_PARTY = 'THIRD_PARTY';

// ── helpers ──────────────────────────────────────────────────────────────────

function span(id, start, end, type = OPERATIONAL, text = `text_${id}`) {
    return { id, start_char: start, end_char: end, redaction_type: type, text };
}

// ── mergeAdjacentSpans ────────────────────────────────────────────────────────

describe('mergeAdjacentSpans', () => {
    it('returns empty array for null input', () => {
        expect(mergeAdjacentSpans(null)).to.deep.equal([]);
    });

    it('returns empty array for empty input', () => {
        expect(mergeAdjacentSpans([])).to.deep.equal([]);
    });

    it('returns a single span unchanged (isMerged: false, ids array)', () => {
        const result = mergeAdjacentSpans([span('a', 0, 5)]);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a']);
        expect(result[0].isMerged).to.be.false;
        expect(result[0].start_char).to.equal(0);
        expect(result[0].end_char).to.equal(5);
    });

    it('merges two immediately adjacent spans of the same type', () => {
        const redactions = [span('a', 0, 5), span('b', 5, 10)];
        const result = mergeAdjacentSpans(redactions);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a', 'b']);
        expect(result[0].isMerged).to.be.true;
        expect(result[0].end_char).to.equal(10);
    });

    it('merges spans within the default gap threshold (gap=2)', () => {
        // gap of exactly 2 characters → should merge
        const redactions = [span('a', 0, 5), span('b', 7, 12)];
        const result = mergeAdjacentSpans(redactions);
        expect(result).to.have.length(1);
        expect(result[0].isMerged).to.be.true;
    });

    it('does NOT merge spans whose gap exceeds the default threshold (gap=3)', () => {
        const redactions = [span('a', 0, 5), span('b', 8, 13)];
        const result = mergeAdjacentSpans(redactions);
        expect(result).to.have.length(2);
        expect(result[0].isMerged).to.be.false;
        expect(result[1].isMerged).to.be.false;
    });

    it('respects a custom gapThreshold', () => {
        const redactions = [span('a', 0, 5), span('b', 10, 15)];

        // Gap is 5 — beyond default (2), but within custom (5)
        const resultTight = mergeAdjacentSpans(redactions, new Set(), 2);
        expect(resultTight).to.have.length(2);

        const resultLoose = mergeAdjacentSpans(redactions, new Set(), 5);
        expect(resultLoose).to.have.length(1);
        expect(resultLoose[0].isMerged).to.be.true;
    });

    it('does NOT merge spans of different types even when adjacent', () => {
        const redactions = [span('a', 0, 5, OPERATIONAL), span('b', 5, 10, THIRD_PARTY)];
        const result = mergeAdjacentSpans(redactions);
        expect(result).to.have.length(2);
        expect(result[0].isMerged).to.be.false;
        expect(result[1].isMerged).to.be.false;
    });

    it('merges three consecutive spans into one', () => {
        const redactions = [span('a', 0, 3), span('b', 3, 6), span('c', 6, 9)];
        const result = mergeAdjacentSpans(redactions);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a', 'b', 'c']);
        expect(result[0].end_char).to.equal(9);
    });

    it('concatenates text with a space when there is a gap > 0', () => {
        // gap of 1 character between 'foo' and 'bar' → 'foo bar'
        const a = { ...span('a', 0, 3), text: 'foo' };
        const b = { ...span('b', 4, 7), text: 'bar' };
        const result = mergeAdjacentSpans([a, b]);
        expect(result[0].text).to.equal('foo bar');
    });

    it('concatenates text without a space when spans are directly adjacent (gap=0)', () => {
        const a = { ...span('a', 0, 3), text: 'foo' };
        const b = { ...span('b', 3, 6), text: 'bar' };
        const result = mergeAdjacentSpans([a, b]);
        expect(result[0].text).to.equal('foobar');
    });

    it('sorts unsorted input before merging', () => {
        // Provide spans in reverse order; they should still merge
        const redactions = [span('b', 5, 10), span('a', 0, 5)];
        const result = mergeAdjacentSpans(redactions);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a', 'b']);
    });

    it('splits a merged item when its key is in splitMerges', () => {
        const redactions = [span('a', 0, 5), span('b', 5, 10)];
        const splitMerges = new Set(['a:b']);
        const result = mergeAdjacentSpans(redactions, splitMerges);
        expect(result).to.have.length(2);
        expect(result[0].ids).to.deep.equal(['a']);
        expect(result[1].ids).to.deep.equal(['b']);
        expect(result[0].isMerged).to.be.false;
        expect(result[1].isMerged).to.be.false;
    });

    it('leaves non-matching split keys unaffected', () => {
        const redactions = [span('a', 0, 5), span('b', 5, 10)];
        const splitMerges = new Set(['x:y']); // does not match 'a:b'
        const result = mergeAdjacentSpans(redactions, splitMerges);
        expect(result).to.have.length(1);
        expect(result[0].isMerged).to.be.true;
    });

    // ── isolatedIds ───────────────────────────────────────────────────────────

    it('merged items include a constituents array with individual id/text pairs', () => {
        const a = { ...span('a', 0, 3), text: 'John' };
        const b = { ...span('b', 4, 7), text: 'Doe' };
        const result = mergeAdjacentSpans([a, b]);
        expect(result[0].constituents).to.deep.equal([
            { id: 'a', text: 'John' },
            { id: 'b', text: 'Doe' },
        ]);
    });

    it('isolating the first item of a 3-way merge leaves the rest merged', () => {
        const redactions = [span('a', 0, 3), span('b', 3, 6), span('c', 6, 9)];
        const result = mergeAdjacentSpans(redactions, new Set(), 2, new Set(['a']));
        expect(result).to.have.length(2);
        expect(result[0].ids).to.deep.equal(['a']);
        expect(result[0].isMerged).to.be.false;
        expect(result[1].ids).to.deep.equal(['b', 'c']);
        expect(result[1].isMerged).to.be.true;
    });

    it('isolating the last item of a 3-way merge leaves the rest merged', () => {
        const redactions = [span('a', 0, 3), span('b', 3, 6), span('c', 6, 9)];
        const result = mergeAdjacentSpans(redactions, new Set(), 2, new Set(['c']));
        expect(result).to.have.length(2);
        expect(result[0].ids).to.deep.equal(['a', 'b']);
        expect(result[0].isMerged).to.be.true;
        expect(result[1].ids).to.deep.equal(['c']);
        expect(result[1].isMerged).to.be.false;
    });

    it('isolating the middle item of a 3-way merge yields three individual items', () => {
        const redactions = [span('a', 0, 3), span('b', 3, 6), span('c', 6, 9)];
        const result = mergeAdjacentSpans(redactions, new Set(), 2, new Set(['b']));
        expect(result).to.have.length(3);
        expect(result[0].ids).to.deep.equal(['a']);
        expect(result[0].isMerged).to.be.false;
        expect(result[1].ids).to.deep.equal(['b']);
        expect(result[1].isMerged).to.be.false;
        expect(result[2].ids).to.deep.equal(['c']);
        expect(result[2].isMerged).to.be.false;
    });

    it('split items retain their original properties', () => {
        const redactions = [
            { id: 'a', start_char: 0, end_char: 5, redaction_type: OPERATIONAL, text: 'hello' },
            { id: 'b', start_char: 5, end_char: 10, redaction_type: OPERATIONAL, text: 'world' },
        ];
        const result = mergeAdjacentSpans(redactions, new Set(['a:b']));
        expect(result[0].text).to.equal('hello');
        expect(result[1].text).to.equal('world');
        expect(result[0].start_char).to.equal(0);
        expect(result[1].end_char).to.equal(10);
    });
});

// ── groupByTextAndType ────────────────────────────────────────────────────────

describe('groupByTextAndType', () => {
    it('returns empty array for empty input', () => {
        expect(groupByTextAndType([])).to.deep.equal([]);
    });

    it('adds isGroup: false to a single unique item', () => {
        const items = [{ id: 'a', text: 'John', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false }];
        const result = groupByTextAndType(items);
        expect(result).to.have.length(1);
        expect(result[0].isGroup).to.be.false;
        expect(result[0].id).to.equal('a');
    });

    it('groups two items with the same text and type', () => {
        const items = [
            { id: 'a', text: 'John', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false },
            { id: 'b', text: 'John', redaction_type: OPERATIONAL, ids: ['b'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
        expect(result).to.have.length(1);
        expect(result[0].isGroup).to.be.true;
        expect(result[0].items).to.have.length(2);
        expect(result[0].text).to.equal('John');
        expect(result[0].redaction_type).to.equal(OPERATIONAL);
    });

    it('does NOT group items with same text but different types', () => {
        const items = [
            { id: 'a', text: 'John', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false },
            { id: 'b', text: 'John', redaction_type: THIRD_PARTY, ids: ['b'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
        expect(result).to.have.length(2);
        expect(result[0].isGroup).to.be.false;
        expect(result[1].isGroup).to.be.false;
    });

    it('does NOT group items with same type but different text', () => {
        const items = [
            { id: 'a', text: 'John', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false },
            { id: 'b', text: 'Jane', redaction_type: OPERATIONAL, ids: ['b'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
        expect(result).to.have.length(2);
    });

    it('groups case-insensitively (John == john)', () => {
        const items = [
            { id: 'a', text: 'John', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false },
            { id: 'b', text: 'john', redaction_type: OPERATIONAL, ids: ['b'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
        expect(result).to.have.length(1);
        expect(result[0].isGroup).to.be.true;
        expect(result[0].items).to.have.length(2);
    });

    it('preserves original insertion order of groups', () => {
        const items = [
            { id: 'a', text: 'Alpha', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false },
            { id: 'b', text: 'Beta', redaction_type: OPERATIONAL, ids: ['b'], isMerged: false },
            { id: 'c', text: 'Alpha', redaction_type: OPERATIONAL, ids: ['c'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
        // Alpha group appears first (seen first), Beta second
        expect(result).to.have.length(2);
        expect(result[0].isGroup).to.be.true;
        expect(result[0].text).to.equal('Alpha');
        expect(result[1].isGroup).to.be.false;
        expect(result[1].text).to.equal('Beta');
    });

    it('group key is derived from text+type', () => {
        const items = [
            { id: 'a', text: 'X', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false },
            { id: 'b', text: 'X', redaction_type: OPERATIONAL, ids: ['b'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
        expect(result[0].key).to.equal('x::OPERATIONAL');
    });
});
