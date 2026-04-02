import { useState, useCallback } from 'react';
import { createRedaction, updateRedaction, deleteRedaction } from '@/services/redactionService';
import toast from 'react-hot-toast';

export function useManualRedaction({
    documentId,
    extractedText,
    accessToken,
    redactions,
    setRedactions,
    pushHistory,
    activeHighlightType,
}) {
    const [manualRedactionAnchor, setManualRedactionAnchor] = useState(null);
    const [newSelection, setNewSelection] = useState(null);
    const [pendingRedaction, setPendingRedaction] = useState(null);

    const applyUpdates = useCallback((updates) => {
        setRedactions(prev => {
            const m = new Map(updates.map(r => [r.id, r]));
            return prev.map(r => m.has(r.id) ? m.get(r.id) : r);
        });
    }, [setRedactions]);

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

    return {
        manualRedactionAnchor,
        pendingRedaction,
        handleTextSelect,
        handleCreateManualRedaction,
        handleCloseManualRedactionPopover,
        handleOnContextSave,
    };
}
