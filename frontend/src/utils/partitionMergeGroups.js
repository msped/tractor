/**
 * Partitions redactions into display items using server-computed merge pairs.
 *
 * All merge *rules* (gap thresholds, type matching, joiner text) live on the
 * backend (cases/span_merging.py); this module contains only partition
 * mechanics: pair activation, union-find grouping, sorting, and
 * concatenation with the server-provided joiner.
 *
 * A pair is active iff both endpoints are in the section being rendered,
 * neither endpoint is isolated, no blocker is in the section, and both
 * members' current redaction_type still equals the pair's type (guards
 * local type changes between PATCH and the next merge-structure fetch).
 *
 * @param {Array} redactions - Redaction objects in the section being rendered
 * @param {Array} mergePairs - merge_structure.pairs from the API:
 *   { a, b, type, joiner, blockers: [] }
 * @param {Set<string>} splitMerges - Merge keys ("id1:id2:...") the user has split
 * @param {Set<string>} isolatedIds - Ids the user removed from their merge group
 * @returns {Array} Display items: { ids, isMerged, constituents, ...rest }
 */
export function partitionMergeGroups(redactions, mergePairs = [], splitMerges = new Set(), isolatedIds = new Set()) {
    if (!redactions || redactions.length === 0) return [];

    const sorted = [...redactions].sort((a, b) => a.start_char - b.start_char);
    const byId = new Map(sorted.map(r => [r.id, r]));

    // Union-find over active pairs; joiners keyed per pair for text assembly.
    const parent = new Map(sorted.map(r => [r.id, r.id]));
    const find = (id) => {
        let root = id;
        while (parent.get(root) !== root) root = parent.get(root);
        let cur = id;
        while (parent.get(cur) !== root) {
            const next = parent.get(cur);
            parent.set(cur, root);
            cur = next;
        }
        return root;
    };
    const joiners = new Map();

    for (const pair of mergePairs || []) {
        const a = byId.get(pair.a);
        const b = byId.get(pair.b);
        if (!a || !b) continue;
        if (isolatedIds.has(pair.a) || isolatedIds.has(pair.b)) continue;
        if (a.redaction_type !== pair.type || b.redaction_type !== pair.type) continue;
        if ((pair.blockers || []).some(id => byId.has(id))) continue;
        parent.set(find(pair.a), find(pair.b));
        joiners.set(`${pair.a}:${pair.b}`, pair.joiner);
    }

    const groupsByRoot = new Map();
    for (const r of sorted) {
        const root = find(r.id);
        if (!groupsByRoot.has(root)) groupsByRoot.set(root, []);
        groupsByRoot.get(root).push(r);
    }

    const asSingleton = (r) => ({ ...r, ids: [r.id], isMerged: false, constituents: [{ id: r.id, text: r.text }] });

    // Emit items in position order of each group's first member.
    const result = [];
    const emitted = new Set();
    for (const r of sorted) {
        const root = find(r.id);
        if (emitted.has(root)) continue;
        emitted.add(root);

        const members = groupsByRoot.get(root);
        if (members.length === 1) {
            result.push(asSingleton(members[0]));
            continue;
        }

        const mergeKey = members.map(m => m.id).join(':');
        if (splitMerges.has(mergeKey)) {
            result.push(...members.map(asSingleton));
            continue;
        }

        // Active pairs never span an in-section redaction, so consecutive
        // group members always have a direct pair carrying their joiner.
        let text = members[0].text;
        for (let i = 1; i < members.length; i++) {
            const joiner = joiners.get(`${members[i - 1].id}:${members[i].id}`) ?? ' ';
            text += joiner + members[i].text;
        }
        result.push({
            ...members[0],
            ids: members.map(m => m.id),
            constituents: members.map(m => ({ id: m.id, text: m.text })),
            end_char: members[members.length - 1].end_char,
            text,
            isMerged: true,
        });
    }

    return result;
}

/**
 * Groups display items by (text, redaction_type) pairs.
 * Items with the same text+type are collected under a group header.
 * Single-item groups pass through unchanged (with isGroup: false added).
 *
 * @param {Array} displayItems - Output from partitionMergeGroups
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
