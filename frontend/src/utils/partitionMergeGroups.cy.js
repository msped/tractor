import { partitionMergeGroups, groupByTextAndType } from './partitionMergeGroups';
import golden from '../../cypress/fixtures/span_merging_review_golden.json';

const OPERATIONAL = 'OPERATIONAL';

// ── helpers ──────────────────────────────────────────────────────────────────

function span(id, start, end, type = OPERATIONAL, text = `text_${id}`) {
    return { id, start_char: start, end_char: end, redaction_type: type, text };
}

function pair(a, b, { type = OPERATIONAL, joiner = '', blockers = [] } = {}) {
    return { a, b, type, joiner, blockers };
}

// ── partitionMergeGroups ─────────────────────────────────────────────────────

describe('partitionMergeGroups', () => {
    it('returns empty array for null input', () => {
        expect(partitionMergeGroups(null, [])).to.deep.equal([]);
    });

    it('returns empty array for empty input', () => {
        expect(partitionMergeGroups([], [])).to.deep.equal([]);
    });

    it('returns a single span unchanged (isMerged: false, ids array)', () => {
        const result = partitionMergeGroups([span('a', 0, 5)], []);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a']);
        expect(result[0].isMerged).to.be.false;
        expect(result[0].start_char).to.equal(0);
        expect(result[0].end_char).to.equal(5);
    });

    it('merges two spans linked by an active pair', () => {
        const redactions = [span('a', 0, 5), span('b', 5, 10)];
        const result = partitionMergeGroups(redactions, [pair('a', 'b')]);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a', 'b']);
        expect(result[0].isMerged).to.be.true;
        expect(result[0].end_char).to.equal(10);
    });

    it('does not merge without a pair (no rule knowledge client-side)', () => {
        const redactions = [span('a', 0, 5), span('b', 5, 10)];
        const result = partitionMergeGroups(redactions, []);
        expect(result).to.have.length(2);
        expect(result[0].isMerged).to.be.false;
        expect(result[1].isMerged).to.be.false;
    });

    it('ignores pairs whose endpoints are not both in the section', () => {
        const result = partitionMergeGroups([span('a', 0, 5)], [pair('a', 'b')]);
        expect(result).to.have.length(1);
        expect(result[0].isMerged).to.be.false;
    });

    it('ignores pairs with a blocker in the section', () => {
        const redactions = [span('a', 0, 5), span('x', 5, 7), span('b', 7, 12)];
        const result = partitionMergeGroups(redactions, [
            pair('a', 'b', { joiner: ' ', blockers: ['x'] }),
        ]);
        expect(result).to.have.length(3);
        result.forEach(item => expect(item.isMerged).to.be.false);
    });

    it('activates a blocked pair once the blocker leaves the section', () => {
        const redactions = [span('a', 0, 5), span('b', 7, 12)];
        const result = partitionMergeGroups(redactions, [
            pair('a', 'b', { joiner: ' ', blockers: ['x'] }),
        ]);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a', 'b']);
        expect(result[0].isMerged).to.be.true;
    });

    it("ignores pairs whose type no longer matches a member's current type", () => {
        const redactions = [span('a', 0, 5, 'PII'), span('b', 5, 10, OPERATIONAL)];
        const result = partitionMergeGroups(redactions, [pair('a', 'b', { type: 'PII' })]);
        expect(result).to.have.length(2);
    });

    it('chains pairs into one group via union-find', () => {
        const redactions = [span('a', 0, 3), span('b', 3, 6), span('c', 6, 9)];
        const result = partitionMergeGroups(redactions, [pair('a', 'b'), pair('b', 'c')]);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a', 'b', 'c']);
        expect(result[0].end_char).to.equal(9);
    });

    it('concatenates text with the server-provided joiner', () => {
        const a = { ...span('a', 0, 3), text: 'foo' };
        const b = { ...span('b', 4, 7), text: 'bar' };
        const withSpace = partitionMergeGroups([a, b], [pair('a', 'b', { joiner: ' ' })]);
        expect(withSpace[0].text).to.equal('foo bar');

        const without = partitionMergeGroups([a, b], [pair('a', 'b', { joiner: '' })]);
        expect(without[0].text).to.equal('foobar');
    });

    it('sorts unsorted input before grouping', () => {
        const redactions = [span('b', 5, 10), span('a', 0, 5)];
        const result = partitionMergeGroups(redactions, [pair('a', 'b')]);
        expect(result).to.have.length(1);
        expect(result[0].ids).to.deep.equal(['a', 'b']);
    });

    it('splits a merged item when its key is in splitMerges', () => {
        const redactions = [span('a', 0, 5), span('b', 5, 10)];
        const splitMerges = new Set(['a:b']);
        const result = partitionMergeGroups(redactions, [pair('a', 'b')], splitMerges);
        expect(result).to.have.length(2);
        expect(result[0].ids).to.deep.equal(['a']);
        expect(result[1].ids).to.deep.equal(['b']);
        expect(result[0].isMerged).to.be.false;
        expect(result[1].isMerged).to.be.false;
    });

    it('leaves non-matching split keys unaffected', () => {
        const redactions = [span('a', 0, 5), span('b', 5, 10)];
        const splitMerges = new Set(['x:y']);
        const result = partitionMergeGroups(redactions, [pair('a', 'b')], splitMerges);
        expect(result).to.have.length(1);
        expect(result[0].isMerged).to.be.true;
    });

    it('merged items include a constituents array with individual id/text pairs', () => {
        const a = { ...span('a', 0, 3), text: 'John' };
        const b = { ...span('b', 4, 7), text: 'Doe' };
        const result = partitionMergeGroups([a, b], [pair('a', 'b', { joiner: ' ' })]);
        expect(result[0].constituents).to.deep.equal([
            { id: 'a', text: 'John' },
            { id: 'b', text: 'Doe' },
        ]);
    });

    it('isolating the first item of a 3-way merge leaves the rest merged', () => {
        const redactions = [span('a', 0, 3), span('b', 3, 6), span('c', 6, 9)];
        const pairs = [pair('a', 'b'), pair('b', 'c')];
        const result = partitionMergeGroups(redactions, pairs, new Set(), new Set(['a']));
        expect(result).to.have.length(2);
        expect(result[0].ids).to.deep.equal(['a']);
        expect(result[0].isMerged).to.be.false;
        expect(result[1].ids).to.deep.equal(['b', 'c']);
        expect(result[1].isMerged).to.be.true;
    });

    it('isolating the last item of a 3-way merge leaves the rest merged', () => {
        const redactions = [span('a', 0, 3), span('b', 3, 6), span('c', 6, 9)];
        const pairs = [pair('a', 'b'), pair('b', 'c')];
        const result = partitionMergeGroups(redactions, pairs, new Set(), new Set(['c']));
        expect(result).to.have.length(2);
        expect(result[0].ids).to.deep.equal(['a', 'b']);
        expect(result[0].isMerged).to.be.true;
        expect(result[1].ids).to.deep.equal(['c']);
        expect(result[1].isMerged).to.be.false;
    });

    it('isolating the middle item of a 3-way merge yields three individual items', () => {
        const redactions = [span('a', 0, 3), span('b', 3, 6), span('c', 6, 9)];
        const pairs = [pair('a', 'b'), pair('b', 'c')];
        const result = partitionMergeGroups(redactions, pairs, new Set(), new Set(['b']));
        expect(result).to.have.length(3);
        result.forEach(item => expect(item.isMerged).to.be.false);
    });

    it('split items retain their original properties', () => {
        const redactions = [
            { id: 'a', start_char: 0, end_char: 5, redaction_type: OPERATIONAL, text: 'hello' },
            { id: 'b', start_char: 5, end_char: 10, redaction_type: OPERATIONAL, text: 'world' },
        ];
        const result = partitionMergeGroups(redactions, [pair('a', 'b')], new Set(['a:b']));
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
            { id: 'b', text: 'John', redaction_type: 'THIRD_PARTY', ids: ['b'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
        expect(result).to.have.length(2);
        expect(result[0].isGroup).to.be.false;
        expect(result[1].isGroup).to.be.false;
    });

    it('groups case-insensitively (John == john)', () => {
        const items = [
            { id: 'a', text: 'John', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false },
            { id: 'b', text: 'john', redaction_type: OPERATIONAL, ids: ['b'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
        expect(result).to.have.length(1);
        expect(result[0].isGroup).to.be.true;
    });

    it('preserves original insertion order of groups', () => {
        const items = [
            { id: 'a', text: 'Alpha', redaction_type: OPERATIONAL, ids: ['a'], isMerged: false },
            { id: 'b', text: 'Beta', redaction_type: OPERATIONAL, ids: ['b'], isMerged: false },
            { id: 'c', text: 'Alpha', redaction_type: OPERATIONAL, ids: ['c'], isMerged: false },
        ];
        const result = groupByTextAndType(items);
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

// ── golden shared fixture ────────────────────────────────────────────────────
// The backend test (cases/tests/test_span_merging.py) asserts redactions →
// pairs over the same fixture; this asserts pairs → per-section groups. The
// composition equals the old end-to-end mergeRedactionSpans behaviour, and a
// backend test asserts the two fixture copies stay byte-identical.

describe('golden shared fixture', () => {
    const sectionFilters = {
        pending: r => r.is_suggestion && !r.is_accepted && !r.justification,
        accepted: r => r.is_suggestion && r.is_accepted,
        rejected: r => r.is_suggestion && !r.is_accepted && !!r.justification,
        manual: r => !r.is_suggestion,
    };

    Object.entries(sectionFilters).forEach(([section, filter]) => {
        it(`produces the golden display groups for the ${section} section`, () => {
            const items = golden.redactions.filter(filter);
            const result = groupByTextAndType(
                partitionMergeGroups(items, golden.pairs)
            );
            expect(result).to.deep.equal(golden.sections[section]);
        });
    });
});
