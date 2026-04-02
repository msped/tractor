import { useCallback } from 'react';
import { createRedaction, updateRedaction, deleteRedaction } from '@/services/redactionService';
import toast from 'react-hot-toast';

export function useRemoveRedaction({
    documentId,
    extractedText,
    accessToken,
    redactions,
    setRedactions,
    pushHistory,
    displaySections,
}) {
    const applySingle = useCallback((updated) => {
        setRedactions(prev => prev.map(r => r.id === updated.id ? updated : r));
    }, [setRedactions]);

    // Internal helper: perform the remove API call + state update without pushing history.
    const _removeRedactionById = useCallback(async (redactionToRemove) => {
        if (!redactionToRemove.is_suggestion) {
            await deleteRedaction(redactionToRemove.id, accessToken);
            setRedactions(prev => prev.filter(r => r.id !== redactionToRemove.id));
            toast.success("Redaction deleted.");
        } else {
            applySingle(await updateRedaction(
                redactionToRemove.id,
                { is_accepted: false, justification: null },
                accessToken
            ));
            toast.success("Suggestion reverted to pending.");
        }
    }, [accessToken, applySingle, setRedactions]);

    const handleRemoveRedaction = useCallback(async (redactionId) => {
        const snap = redactions.find(r => r.id === redactionId);
        if (!snap) return;
        try {
            await _removeRedactionById(snap);
            if (!snap.is_suggestion) {
                // Manual redaction deleted — undo recreates it
                let currentId = snap.id;
                pushHistory(
                    async () => {
                        const created = await createRedaction(documentId, {
                            text: snap.text,
                            start_char: snap.start_char,
                            end_char: snap.end_char,
                            document: documentId,
                            redaction_type: snap.redaction_type,
                            is_suggestion: false,
                            is_accepted: true,
                        }, accessToken);
                        currentId = created.id;
                        setRedactions(prev => [...prev, created]);
                    },
                    async () => {
                        await deleteRedaction(currentId, accessToken);
                        setRedactions(prev => prev.filter(r => r.id !== currentId));
                    }
                );
            } else {
                // AI suggestion reverted to pending — undo restores prior state
                pushHistory(
                    async () => applySingle(await updateRedaction(snap.id, { is_accepted: snap.is_accepted, justification: snap.justification }, accessToken)),
                    async () => applySingle(await updateRedaction(snap.id, { is_accepted: false, justification: null }, accessToken))
                );
            }
        } catch (error) {
            toast.error("Failed to remove redaction. Please try again.");
        }
    }, [redactions, accessToken, pushHistory, _removeRedactionById, documentId, applySingle, setRedactions]);

    // When Remove tool is active and text is selected, trim/remove the overlapping accepted redaction(s).
    const handleRemoveSelect = useCallback(async (selection) => {
        const selStart = selection.start_char;
        const selEnd = selection.end_char;

        const overlapping = redactions.filter(r =>
            (r.is_accepted || !r.is_suggestion) &&
            r.start_char < selEnd && r.end_char > selStart
        );

        if (overlapping.length === 0) return;

        const snapshots = overlapping.map(r => ({ ...r }));

        // For split operations a new record is created; track its ID so undo can delete it.
        // Using a mutable ref-style variable so redo can keep it current after re-creation.
        let splitCreatedId = null;

        try {
            for (const r of overlapping) {
                const fullyContained = selStart <= r.start_char && selEnd >= r.end_char;
                const trimEnd = !fullyContained && selEnd >= r.end_char;
                const trimStart = !fullyContained && selStart <= r.start_char;
                const splitMiddle = !fullyContained && !trimEnd && !trimStart;

                if (fullyContained) {
                    if (!r.is_suggestion) {
                        await deleteRedaction(r.id, accessToken);
                        setRedactions(prev => prev.filter(x => x.id !== r.id));
                    } else {
                        applySingle(await updateRedaction(r.id, { is_accepted: false, justification: null }, accessToken));
                    }
                } else if (trimEnd) {
                    applySingle(await updateRedaction(r.id, {
                        end_char: selStart,
                        text: extractedText.substring(r.start_char, selStart),
                    }, accessToken));
                } else if (trimStart) {
                    applySingle(await updateRedaction(r.id, {
                        start_char: selEnd,
                        text: extractedText.substring(selEnd, r.end_char),
                    }, accessToken));
                } else if (splitMiddle) {
                    applySingle(await updateRedaction(r.id, {
                        end_char: selStart,
                        text: extractedText.substring(r.start_char, selStart),
                    }, accessToken));
                    const createdSecond = await createRedaction(documentId, {
                        text: extractedText.substring(selEnd, r.end_char),
                        start_char: selEnd,
                        end_char: r.end_char,
                        document: documentId,
                        redaction_type: r.redaction_type,
                        is_suggestion: r.is_suggestion,
                        is_accepted: r.is_accepted,
                        justification: r.justification,
                    }, accessToken);
                    setRedactions(prev => [...prev, createdSecond]);
                    splitCreatedId = createdSecond.id;
                }
            }
        } catch {
            toast.error("Failed to modify redaction. Please try again.");
            return;
        }

        pushHistory(
            async () => {
                // Undo: restore all original positions/state
                for (const snap of snapshots) {
                    const fullyContained = selStart <= snap.start_char && selEnd >= snap.end_char;
                    const splitMiddle = !fullyContained && selStart > snap.start_char && selEnd < snap.end_char;

                    if (fullyContained) {
                        if (!snap.is_suggestion) {
                            const created = await createRedaction(documentId, {
                                text: snap.text, start_char: snap.start_char, end_char: snap.end_char,
                                document: documentId, redaction_type: snap.redaction_type,
                                is_suggestion: false, is_accepted: true,
                            }, accessToken);
                            setRedactions(prev => [...prev, created]);
                        } else {
                            applySingle(await updateRedaction(snap.id, { is_accepted: snap.is_accepted, justification: snap.justification }, accessToken));
                        }
                    } else {
                        applySingle(await updateRedaction(snap.id, {
                            start_char: snap.start_char, end_char: snap.end_char, text: snap.text,
                        }, accessToken));
                        if (splitMiddle && splitCreatedId) {
                            await deleteRedaction(splitCreatedId, accessToken);
                            setRedactions(prev => prev.filter(r => r.id !== splitCreatedId));
                            splitCreatedId = null;
                        }
                    }
                }
            },
            async () => {
                // Redo: re-apply the trim/remove operations
                for (const snap of snapshots) {
                    const fullyContained = selStart <= snap.start_char && selEnd >= snap.end_char;
                    const trimEnd = !fullyContained && selEnd >= snap.end_char;
                    const trimStart = !fullyContained && selStart <= snap.start_char;
                    const splitMiddle = !fullyContained && !trimEnd && !trimStart;

                    if (fullyContained) {
                        if (!snap.is_suggestion) {
                            await deleteRedaction(snap.id, accessToken);
                            setRedactions(prev => prev.filter(r => r.id !== snap.id));
                        } else {
                            applySingle(await updateRedaction(snap.id, { is_accepted: false, justification: null }, accessToken));
                        }
                    } else if (trimEnd) {
                        applySingle(await updateRedaction(snap.id, {
                            end_char: selStart, text: extractedText.substring(snap.start_char, selStart),
                        }, accessToken));
                    } else if (trimStart) {
                        applySingle(await updateRedaction(snap.id, {
                            start_char: selEnd, text: extractedText.substring(selEnd, snap.end_char),
                        }, accessToken));
                    } else if (splitMiddle) {
                        applySingle(await updateRedaction(snap.id, {
                            end_char: selStart, text: extractedText.substring(snap.start_char, selStart),
                        }, accessToken));
                        const created = await createRedaction(documentId, {
                            text: extractedText.substring(selEnd, snap.end_char),
                            start_char: selEnd, end_char: snap.end_char,
                            document: documentId, redaction_type: snap.redaction_type,
                            is_suggestion: snap.is_suggestion, is_accepted: snap.is_accepted,
                            justification: snap.justification,
                        }, accessToken);
                        setRedactions(prev => [...prev, created]);
                        splitCreatedId = created.id;
                    }
                }
            }
        );
    }, [redactions, pushHistory, accessToken, documentId, extractedText, applySingle, setRedactions]);

    // When the REMOVE tool is active and a highlight is clicked in the document,
    // find all IDs in the same merge group and remove them as a single undo step.
    const handleUnhighlightClick = useCallback(async (clickedId) => {
        let targetIds = [clickedId];
        outer: for (const section of Object.values(displaySections)) {
            for (const item of section.items) {
                const candidates = item.isGroup
                    ? item.items.flatMap(gi => gi.ids ?? [gi.id])
                    : (item.ids ?? [item.id]);
                if (candidates.includes(clickedId)) {
                    targetIds = candidates;
                    break outer;
                }
            }
        }

        const snapshots = targetIds.map(id => redactions.find(r => r.id === id)).filter(Boolean);
        if (snapshots.length === 0) return;

        try {
            await Promise.all(snapshots.map(snap => _removeRedactionById(snap)));
        } catch {
            toast.error("Failed to remove redaction. Please try again.");
            return;
        }

        pushHistory(
            async () => {
                for (const snap of snapshots) {
                    if (!snap.is_suggestion) {
                        const created = await createRedaction(documentId, {
                            text: snap.text,
                            start_char: snap.start_char,
                            end_char: snap.end_char,
                            document: documentId,
                            redaction_type: snap.redaction_type,
                            is_suggestion: false,
                            is_accepted: true,
                        }, accessToken);
                        setRedactions(prev => [...prev, created]);
                    } else {
                        const restored = await updateRedaction(snap.id, { is_accepted: snap.is_accepted, justification: snap.justification }, accessToken);
                        setRedactions(prev => prev.map(r => r.id === snap.id ? restored : r));
                    }
                }
            },
            async () => {
                await Promise.all(snapshots.map(snap => _removeRedactionById(snap)));
            }
        );
    }, [displaySections, redactions, pushHistory, _removeRedactionById, documentId, accessToken, setRedactions]);

    return {
        handleRemoveRedaction,
        handleRemoveSelect,
        handleUnhighlightClick,
    };
}
