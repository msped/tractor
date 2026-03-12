/**
 * Merges adjacent or near-adjacent redaction spans of the same type into
 * compound display items. The underlying DB records are not changed.
 *
 * @param {Array} redactions - Raw redaction objects from the DB
 * @param {Set<string>} splitMerges - Merge keys ("id1:id2") the user has split
 * @param {number} gapThreshold - Max character gap to consider spans adjacent
 * @returns {Array} Display items: { ids, isMerged, ...rest }
 */
export function mergeAdjacentSpans(redactions, splitMerges = new Set(), gapThreshold = 2) {
    if (!redactions || redactions.length === 0) return [];

    const sorted = [...redactions].sort((a, b) => a.start_char - b.start_char);
    const merged = [];

    let current = { ...sorted[0], ids: [sorted[0].id], isMerged: false };

    for (let i = 1; i < sorted.length; i++) {
        const next = sorted[i];
        const gap = next.start_char - current.end_char;

        if (gap <= gapThreshold && next.redaction_type === current.redaction_type) {
            current = {
                ...current,
                ids: [...current.ids, next.id],
                end_char: next.end_char,
                text: current.text + (gap > 0 ? ' ' : '') + next.text,
                isMerged: true,
            };
        } else {
            merged.push(current);
            current = { ...next, ids: [next.id], isMerged: false };
        }
    }
    merged.push(current);

    // Expand any merges the user has chosen to split back into individual items
    const result = [];
    for (const item of merged) {
        const mergeKey = item.ids.join(':');
        if (item.isMerged && splitMerges.has(mergeKey)) {
            for (const id of item.ids) {
                const original = redactions.find(r => r.id === id);
                if (original) {
                    result.push({ ...original, ids: [original.id], isMerged: false });
                }
            }
        } else {
            result.push(item);
        }
    }

    return result;
}

/**
 * Groups display items by (text, redaction_type) pairs.
 * Items with the same text+type are collected under a group header.
 * Single-item groups pass through unchanged (with isGroup: false added).
 *
 * @param {Array} displayItems - Output from mergeAdjacentSpans
 * @returns {Array} Items with isGroup flag; groups have
 *   { key, items, isGroup: true, text, redaction_type }
 */
export function groupByTextAndType(displayItems) {
    const groupMap = new Map();
    const keyOrder = [];

    for (const item of displayItems) {
        const key = item.text.toLowerCase() + '::' + item.redaction_type;
        if (!groupMap.has(key)) {
            groupMap.set(key, []);
            keyOrder.push(key);
        }
        groupMap.get(key).push(item);
    }

    return keyOrder.map(key => {
        const items = groupMap.get(key);
        if (items.length === 1) {
            return { ...items[0], isGroup: false };
        }
        return {
            key,
            items,
            isGroup: true,
            text: items[0].text,
            redaction_type: items[0].redaction_type,
        };
    });
}
