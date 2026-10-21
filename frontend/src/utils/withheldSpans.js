/**
 * Whose characters win when two accepted redactions cover the same text.
 *
 * The browser-side mirror of `cases/disclosure.py`. The final-preview pane
 * shows the reviewer what the data subject will receive, so it has to resolve
 * overlaps exactly as the export does: DS_INFO is disclosed, and a span
 * overlapping it is cut back to the characters DS_INFO does not claim —
 * split in two where the claim is interior.
 *
 * Dropping DS_INFO rows alone (which is all the preview used to do) only
 * honours the decision when spans coincide exactly; on a partial overlap the
 * wider span still covers the characters and the preview blacks out the data
 * subject's own name while claiming to show the disclosure copy.
 *
 * Keep the two implementations in step — `cases/tests/test_disclosure.py`
 * and `withheldSpans.cy.js` cover the same cases on purpose.
 */

const DS_INFO = 'DS_INFO';

/** Collapse [start, end) pairs into sorted, non-overlapping ranges. */
const mergeRanges = (ranges) => {
    const merged = [];
    [...ranges]
        .sort((a, b) => a[0] - b[0] || a[1] - b[1])
        .forEach(([start, end]) => {
            if (end <= start) return;
            const last = merged[merged.length - 1];
            if (last && start <= last[1]) {
                last[1] = Math.max(last[1], end);
            } else {
                merged.push([start, end]);
            }
        });
    return merged;
};

/** The parts of [start, end) left once every disclosed range is removed. */
const subtract = (start, end, disclosed) => {
    const remaining = [];
    let cursor = start;
    for (const [dStart, dEnd] of disclosed) {
        if (dEnd <= cursor) continue;
        if (dStart >= end) break;
        if (dStart > cursor) remaining.push([cursor, dStart]);
        cursor = Math.max(cursor, dEnd);
        if (cursor >= end) break;
    }
    if (cursor < end) remaining.push([cursor, end]);
    return remaining;
};

/** The character ranges accepted DS_INFO claims, merged and sorted. */
export const disclosedRanges = (redactions) =>
    mergeRanges(
        redactions
            .filter(r => r.redaction_type === DS_INFO)
            .map(r => [r.start_char, r.end_char])
    );

/**
 * Resolve redactions into the spans a disclosure copy should withhold.
 *
 * Drops DS_INFO and cuts every other span back to the characters DS_INFO does
 * not claim. A span wholly claimed disappears; one claimed through the middle
 * comes back as two pieces, each keeping the original's id and type so the
 * renderer can still key and colour them.
 */
export const withheldSpans = (redactions) => {
    const disclosed = disclosedRanges(redactions);
    const pieces = [];

    redactions.forEach(r => {
        if (r.redaction_type === DS_INFO) return;

        const remaining = subtract(r.start_char, r.end_char, disclosed);
        if (
            remaining.length === 1
            && remaining[0][0] === r.start_char
            && remaining[0][1] === r.end_char
        ) {
            // Nothing was claimed from it — keep the row itself.
            pieces.push(r);
            return;
        }

        remaining.forEach(([start, end]) => {
            pieces.push({ ...r, start_char: start, end_char: end });
        });
    });

    return pieces.sort((a, b) => a.start_char - b.start_char || a.end_char - b.end_char);
};
