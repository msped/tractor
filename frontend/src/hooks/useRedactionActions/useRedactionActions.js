import { useCallback } from 'react';
import { updateRedaction, bulkUpdateRedactions } from '@/services/redactionService';
import toast from 'react-hot-toast';

export function useRedactionActions({
    documentId,
    accessToken,
    redactions,
    setRedactions,
    pushHistory,
    setSplitMerges,
    setScrollToId,
    bulkRejectIds,
    setBulkRejectIds,
    setRejectionDialogOpen,
    setRejectionTarget,
}) {
    const applyUpdates = useCallback((updates) => {
        setRedactions(prev => {
            const m = new Map(updates.map(r => [r.id, r]));
            return prev.map(r => m.has(r.id) ? m.get(r.id) : r);
        });
    }, [setRedactions]);

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

    return {
        handleAcceptSuggestion,
        handleBulkAccept,
        handleRejectAsDisclosable,
        handleChangeTypeAndAccept,
        handleBulkChangeTypeAndAccept,
        handleOpenRejectDialog,
        handleOpenBulkRejectDialog,
        handleRejectConfirm,
        handleSplitMerge,
    };
}
