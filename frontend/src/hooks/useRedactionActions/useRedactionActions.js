import { useState, useCallback } from 'react';
import { createRedaction, updateRedaction, deleteRedaction, bulkUpdateRedactions } from '@/services/redactionService';
import toast from 'react-hot-toast';

export function useRedactionActions({
    documentId,
    extractedText,
    accessToken,
    redactions,
    setRedactions,
    pushHistory,
    setSplitMerges,
    displaySections,
    activeHighlightType,
    setScrollToId,
    bulkRejectIds,
    setBulkRejectIds,
    setRejectionDialogOpen,
    setRejectionTarget,
}) {
    const [manualRedactionAnchor, setManualRedactionAnchor] = useState(null);
    const [newSelection, setNewSelection] = useState(null);
    const [pendingRedaction, setPendingRedaction] = useState(null);

    // Merge an array of updated redaction objects into state by id.
    const applyUpdates = useCallback((updates) => {
        setRedactions(prev => {
            const m = new Map(updates.map(r => [r.id, r]));
            return prev.map(r => m.has(r.id) ? m.get(r.id) : r);
        });
    }, [setRedactions]);

    // Replace a single redaction in state (matched by updated.id).
    const applySingle = useCallback((updated) => {
        setRedactions(prev => prev.map(r => r.id === updated.id ? updated : r));
    }, [setRedactions]);

    const handleAcceptSuggestion = useCallback(async (redactionId) => {
        setScrollToId(null);
        const prev = redactions.find(r => r.id === redactionId);
        if (!prev) return;
        try {
            const updatedRedaction = await updateRedaction(
                redactionId, { is_accepted: true },
                accessToken
            );
            applySingle(updatedRedaction);
            pushHistory(
                async () => applySingle(await updateRedaction(redactionId, { is_accepted: false, justification: null }, accessToken)),
                async () => applySingle(await updateRedaction(redactionId, { is_accepted: true }, accessToken))
            );
        } catch (error) {
            toast.error("Failed to accept suggestion. Please try again.");
        }
    }, [redactions, accessToken, pushHistory, applySingle, setScrollToId]);

    const handleBulkAccept = useCallback(async (ids) => {
        setScrollToId(null);
        try {
            const updatedRedactions = await bulkUpdateRedactions(
                documentId, ids, true, null, accessToken
            );
            applyUpdates(updatedRedactions);
            pushHistory(
                async () => applyUpdates(await bulkUpdateRedactions(documentId, ids, false, null, accessToken)),
                async () => applyUpdates(await bulkUpdateRedactions(documentId, ids, true, null, accessToken))
            );
        } catch (error) {
            toast.error("Failed to accept suggestions. Please try again.");
        }
    }, [documentId, accessToken, pushHistory, applyUpdates, setScrollToId]);

    const handleRejectAsDisclosable = useCallback(async (ids, justification) => {
        setScrollToId(null);
        try {
            if (ids.length === 1) {
                const updated = await updateRedaction(
                    ids[0], { is_accepted: false, justification }, accessToken
                );
                applySingle(updated);
                pushHistory(
                    async () => applySingle(await updateRedaction(ids[0], { is_accepted: false, justification: null }, accessToken)),
                    async () => applySingle(await updateRedaction(ids[0], { is_accepted: false, justification }, accessToken))
                );
            } else {
                const updatedList = await bulkUpdateRedactions(
                    documentId, ids, false, justification, accessToken
                );
                applyUpdates(updatedList);
                pushHistory(
                    async () => applyUpdates(await bulkUpdateRedactions(documentId, ids, false, null, accessToken)),
                    async () => applyUpdates(await bulkUpdateRedactions(documentId, ids, false, justification, accessToken))
                );
            }
        } catch (error) {
            toast.error("Failed to reject suggestion. Please try again.");
        }
    }, [documentId, accessToken, pushHistory, applySingle, applyUpdates, setScrollToId]);

    const handleChangeTypeAndAccept = useCallback(async (redactionId, newType) => {
        setScrollToId(null);
        const prev = redactions.find(r => r.id === redactionId);
        if (!prev) return;
        const originalType = prev.redaction_type;
        const originalIsAccepted = prev.is_accepted;
        const originalIsSuggestion = prev.is_suggestion;
        try {
            const updatedRedaction = await updateRedaction(
                redactionId,
                { redaction_type: newType, is_accepted: true, is_suggestion: false },
                accessToken
            );
            applySingle(updatedRedaction);
            toast.success("Suggestion type changed and accepted.");
            pushHistory(
                async () => applySingle(await updateRedaction(redactionId, { redaction_type: originalType, is_accepted: originalIsAccepted, is_suggestion: originalIsSuggestion }, accessToken)),
                async () => applySingle(await updateRedaction(redactionId, { redaction_type: newType, is_accepted: true, is_suggestion: false }, accessToken))
            );
        } catch (error) {
            toast.error("Failed to change suggestion type. Please try again.");
        }
    }, [redactions, accessToken, pushHistory, applySingle, setScrollToId]);

    const handleBulkChangeTypeAndAccept = useCallback(async (ids, newType) => {
        setScrollToId(null);
        const originals = ids.map(id => redactions.find(r => r.id === id)).filter(Boolean);
        try {
            const updates = await Promise.all(
                ids.map(id => updateRedaction(id, { redaction_type: newType, is_accepted: true, is_suggestion: false }, accessToken))
            );
            applyUpdates(updates);
            toast.success("Suggestions type changed and accepted.");
            pushHistory(
                async () => applyUpdates(await Promise.all(
                    originals.map(o => updateRedaction(o.id, { redaction_type: o.redaction_type, is_accepted: o.is_accepted, is_suggestion: o.is_suggestion }, accessToken))
                )),
                async () => applyUpdates(await Promise.all(
                    ids.map(id => updateRedaction(id, { redaction_type: newType, is_accepted: true, is_suggestion: false }, accessToken))
                ))
            );
        } catch (error) {
            toast.error("Failed to change suggestion types. Please try again.");
        }
    }, [redactions, accessToken, pushHistory, applyUpdates, setScrollToId]);

    const handleOpenRejectDialog = useCallback((redaction) => {
        setBulkRejectIds([]);
        setRejectionTarget(redaction);
        setRejectionDialogOpen(true);
    }, [setBulkRejectIds, setRejectionTarget, setRejectionDialogOpen]);

    const handleOpenBulkRejectDialog = useCallback((ids) => {
        setBulkRejectIds(ids);
        setRejectionTarget({ id: null, text: `${ids.length} selected items` });
        setRejectionDialogOpen(true);
    }, [setBulkRejectIds, setRejectionTarget, setRejectionDialogOpen]);

    const handleRejectConfirm = useCallback(async (redactionId, reason) => {
        setScrollToId(null);
        if (bulkRejectIds.length > 0) {
            const capturedIds = [...bulkRejectIds];
            try {
                const updatedRedactions = await bulkUpdateRedactions(
                    documentId, capturedIds, false, reason, accessToken
                );
                applyUpdates(updatedRedactions);
                pushHistory(
                    async () => applyUpdates(await bulkUpdateRedactions(documentId, capturedIds, false, null, accessToken)),
                    async () => applyUpdates(await bulkUpdateRedactions(documentId, capturedIds, false, reason, accessToken))
                );
            } catch (error) {
                toast.error("Failed to reject suggestions. Please try again.");
            } finally {
                setRejectionDialogOpen(false);
                setRejectionTarget(null);
                setBulkRejectIds([]);
            }
        } else {
            try {
                const updatedRedaction = await updateRedaction(
                    redactionId,
                    { is_accepted: false, justification: reason },
                    accessToken
                );
                applySingle(updatedRedaction);
                pushHistory(
                    async () => applySingle(await updateRedaction(redactionId, { is_accepted: false, justification: null }, accessToken)),
                    async () => applySingle(await updateRedaction(redactionId, { is_accepted: false, justification: reason }, accessToken))
                );
            } catch (error) {
                toast.error("Failed to reject suggestion. Please try again.");
            } finally {
                setRejectionDialogOpen(false);
                setRejectionTarget(null);
            }
        }
    }, [bulkRejectIds, documentId, accessToken, pushHistory, applySingle, applyUpdates, setScrollToId, setRejectionDialogOpen, setRejectionTarget, setBulkRejectIds]);

    const handleSplitMerge = useCallback((mergeKey) => {
        setSplitMerges(prev => new Set(prev).add(mergeKey));
        pushHistory(
            async () => setSplitMerges(prev => { const n = new Set(prev); n.delete(mergeKey); return n; }),
            async () => setSplitMerges(prev => new Set(prev).add(mergeKey))
        );
    }, [pushHistory, setSplitMerges]);

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

    const handleCloseManualRedactionPopover = useCallback(() => {
        setManualRedactionAnchor(null);
        setNewSelection(null);
        setPendingRedaction(null);
    }, []);

    const handleOnContextSave = useCallback((redactionId, newContextText) => {
        setRedactions(prevRedactions =>
            prevRedactions.map(r => {
                if (r.id === redactionId) {
                    return { ...r, context: newContextText ? { text: newContextText } : null };
                }
                return r;
            })
        );
    }, [setRedactions]);

    const handleCreateManualRedaction = useCallback(async (redactionType, selectionOverride = null) => {
        if (redactionType === 'REMOVE') return;
        const sel = selectionOverride ?? newSelection;
        const isToolMode = selectionOverride !== null;
        if (!sel) return;

        // Find any existing redactions that overlap with the selection
        const overlapping = redactions.filter(r =>
            r.start_char < sel.end_char && r.end_char > sel.start_char
        );

        if (overlapping.length > 0) {
            if (isToolMode) {
                // Tool mode: accept/update every overlapping redaction, preserving is_suggestion,
                // then create new user redactions for any uncovered gaps within the selection.
                const originalOverlapping = overlapping.map(r => ({ id: r.id, redaction_type: r.redaction_type, is_accepted: r.is_accepted, is_suggestion: r.is_suggestion }));
                let currentCreatedIds = [];
                try {
                    applyUpdates(await Promise.all(
                        overlapping.map(r => updateRedaction(r.id, { redaction_type: redactionType, is_accepted: true }, accessToken))
                    ));
                } catch (error) {
                    handleCloseManualRedactionPopover();
                    toast.error("Failed to update redactions. Please try again.");
                    return;
                }

                // Find gaps within the selection not covered by any overlapping redaction
                const sorted = [...overlapping].sort((a, b) => a.start_char - b.start_char);
                const gaps = [];
                let cursor = sel.start_char;
                for (const r of sorted) {
                    const rStart = Math.max(r.start_char, sel.start_char);
                    if (rStart > cursor) gaps.push({ start_char: cursor, end_char: rStart });
                    cursor = Math.max(cursor, Math.min(r.end_char, sel.end_char));
                }
                if (cursor < sel.end_char) gaps.push({ start_char: cursor, end_char: sel.end_char });

                // Creates redactions for any substantive gap ranges, adds them to state, and
                // returns their IDs (so callers can track them for undo/redo).
                const fillGaps = async (gapList) => {
                    const docText = extractedText || '';
                    const substantiveGaps = gapList.filter(gap =>
                        docText.substring(gap.start_char, gap.end_char).trim().length > 0
                    );
                    if (substantiveGaps.length === 0) return [];
                    const created = await Promise.all(
                        substantiveGaps.map(gap => createRedaction(documentId, {
                            text: docText.substring(gap.start_char, gap.end_char),
                            start_char: gap.start_char,
                            end_char: gap.end_char,
                            document: documentId,
                            redaction_type: redactionType,
                            is_suggestion: false,
                            is_accepted: true,
                        }, accessToken))
                    );
                    setRedactions(prev => [...prev, ...created]);
                    return created.map(r => r.id);
                };

                if (gaps.length > 0) {
                    try {
                        currentCreatedIds = await fillGaps(gaps);
                    } catch (error) {
                        toast.error("Failed to redact uncovered areas. Please try again.");
                    }
                }

                pushHistory(
                    async () => {
                        // Delete gap-filled redactions, then revert the updated overlapping ones
                        await Promise.all(currentCreatedIds.map(id => deleteRedaction(id, accessToken)));
                        setRedactions(prev => prev.filter(r => !currentCreatedIds.includes(r.id)));
                        applyUpdates(await Promise.all(
                            originalOverlapping.map(o => updateRedaction(o.id, { redaction_type: o.redaction_type, is_accepted: o.is_accepted }, accessToken))
                        ));
                    },
                    async () => {
                        applyUpdates(await Promise.all(
                            originalOverlapping.map(o => updateRedaction(o.id, { redaction_type: redactionType, is_accepted: true }, accessToken))
                        ));
                        if (gaps.length > 0) currentCreatedIds = await fillGaps(gaps);
                    }
                );

                handleCloseManualRedactionPopover();
                return;
            }

            // Popover mode
            const sameType = overlapping.every(r => r.redaction_type === redactionType);
            if (sameType) {
                handleCloseManualRedactionPopover();
                toast("This text is already redacted with this classification.");
                return;
            }
            // Different classification — overwrite the existing redaction(s)
            const originalOverlapping = overlapping.map(r => ({ id: r.id, redaction_type: r.redaction_type, is_accepted: r.is_accepted, is_suggestion: r.is_suggestion }));
            try {
                applyUpdates(await Promise.all(
                    overlapping.map(r => updateRedaction(r.id, { redaction_type: redactionType, is_accepted: true, is_suggestion: false }, accessToken))
                ));
                handleCloseManualRedactionPopover();
                toast.success("Redaction classification updated.");
                pushHistory(
                    async () => applyUpdates(await Promise.all(
                        originalOverlapping.map(o => updateRedaction(o.id, { redaction_type: o.redaction_type, is_accepted: o.is_accepted, is_suggestion: o.is_suggestion }, accessToken))
                    )),
                    async () => applyUpdates(await Promise.all(
                        originalOverlapping.map(o => updateRedaction(o.id, { redaction_type: redactionType, is_accepted: true, is_suggestion: false }, accessToken))
                    ))
                );
            } catch (error) {
                handleCloseManualRedactionPopover();
                toast.error("Failed to update redaction. Please try again.");
            }
            return;
        }

        const newRedaction = {
            ...sel,
            document: documentId,
            redaction_type: redactionType,
            is_suggestion: false,
            is_accepted: true,
        };
        let currentCreatedId = null;
        try {
            const createdRedaction = await createRedaction(documentId, newRedaction, accessToken);
            currentCreatedId = createdRedaction.id;
            setRedactions(prev => [...prev, createdRedaction]);
            handleCloseManualRedactionPopover();
            toast.success("Redaction created successfully.");
            pushHistory(
                async () => {
                    await deleteRedaction(currentCreatedId, accessToken);
                    setRedactions(prev => prev.filter(r => r.id !== currentCreatedId));
                },
                async () => {
                    const reCreated = await createRedaction(documentId, newRedaction, accessToken);
                    currentCreatedId = reCreated.id;
                    setRedactions(prev => [...prev, reCreated]);
                }
            );
        } catch (error) {
            handleCloseManualRedactionPopover();
            toast.error("Failed to create redaction. Please try again.");
        }
    }, [newSelection, documentId, extractedText, handleCloseManualRedactionPopover, accessToken, redactions, pushHistory, applyUpdates, setRedactions]);

    const handleTextSelect = useCallback((selection, rect) => {
        if (activeHighlightType === 'REMOVE') return;
        if (activeHighlightType) {
            setNewSelection(selection);
            setPendingRedaction(selection);
            handleCreateManualRedaction(activeHighlightType, selection);
            return;
        }
        setNewSelection(selection);
        setPendingRedaction(selection);
        const virtualEl = { getBoundingClientRect: () => rect, nodeType: 1 };
        setManualRedactionAnchor(virtualEl);
    }, [activeHighlightType, handleCreateManualRedaction]);

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
        manualRedactionAnchor,
        pendingRedaction,
        handleAcceptSuggestion,
        handleBulkAccept,
        handleRejectAsDisclosable,
        handleChangeTypeAndAccept,
        handleBulkChangeTypeAndAccept,
        handleOpenRejectDialog,
        handleOpenBulkRejectDialog,
        handleRejectConfirm,
        handleSplitMerge,
        handleRemoveRedaction,
        handleUnhighlightClick,
        handleOnContextSave,
        handleCreateManualRedaction,
        handleCloseManualRedactionPopover,
        handleTextSelect,
        handleRemoveSelect,
    };
}
