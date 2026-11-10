import { useCallback } from 'react';
import { updateRedaction, bulkUpdateRedactions } from '@/services/redactionService';
import toast from 'react-hot-toast';
import { toastError } from '@/api/toastError';

export function useRedactionActions({
    documentId,
    redactions,
    setRedactions,
    pushHistory,
    setSplitMerges,
    setIsolatedIds,
    setScrollToId,
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
                redactionId, { is_accepted: true }
            );
            applySingle(updatedRedaction);
            pushHistory(
                async () => applySingle(await updateRedaction(redactionId, { is_accepted: false, justification: null })),
                async () => applySingle(await updateRedaction(redactionId, { is_accepted: true }))
            );
        } catch (error) {
            toastError(error, "Failed to accept suggestion. Please try again.");
        }
    }, [redactions, pushHistory, applySingle, setScrollToId]);

    const handleBulkAccept = useCallback(async (ids) => {
        setScrollToId(null);
        try {
            const updatedRedactions = await bulkUpdateRedactions(
                documentId, ids, true, null
            );
            applyUpdates(updatedRedactions);
            pushHistory(
                async () => applyUpdates(await bulkUpdateRedactions(documentId, ids, false, null)),
                async () => applyUpdates(await bulkUpdateRedactions(documentId, ids, true, null))
            );
        } catch (error) {
            toastError(error, "Failed to accept suggestions. Please try again.");
        }
    }, [documentId, pushHistory, applyUpdates, setScrollToId]);

    // A reject needs no reason, so it carries `rejected: true`; a write with
    // neither that nor a reason is read by the server as withdrawing the decision.
    const handleReject = useCallback(async (redaction) => {
        setScrollToId(null);
        try {
            const updated = await updateRedaction(redaction.id, { is_accepted: false, rejected: true });
            applySingle(updated);
            pushHistory(
                async () => applySingle(await updateRedaction(redaction.id, { is_accepted: false, justification: null })),
                async () => applySingle(await updateRedaction(redaction.id, { is_accepted: false, rejected: true }))
            );
        } catch (error) {
            toastError(error, "Failed to reject suggestion. Please try again.");
        }
    }, [pushHistory, applySingle, setScrollToId]);

    const handleBulkReject = useCallback(async (ids) => {
        setScrollToId(null);
        try {
            const updatedList = await bulkUpdateRedactions(documentId, ids, false, null, { rejected: true });
            applyUpdates(updatedList);
            pushHistory(
                async () => applyUpdates(await bulkUpdateRedactions(documentId, ids, false, null)),
                async () => applyUpdates(await bulkUpdateRedactions(documentId, ids, false, null, { rejected: true }))
            );
        } catch (error) {
            toastError(error, "Failed to reject suggestions. Please try again.");
        }
    }, [documentId, pushHistory, applyUpdates, setScrollToId]);

    // The exemption is stored as the template name in `justification`. The bulk
    // endpoint clears justification on accept, so each id is written on its own.
    const handleAcceptWithExemption = useCallback(async (ids, justification) => {
        setScrollToId(null);
        const acceptAll = () => Promise.all(
            ids.map(id => updateRedaction(id, { is_accepted: true, justification }))
        );
        try {
            applyUpdates(await acceptAll());
            pushHistory(
                async () => applyUpdates(await Promise.all(
                    ids.map(id => updateRedaction(id, { is_accepted: false, justification: null }))
                )),
                async () => applyUpdates(await acceptAll())
            );
        } catch (error) {
            toastError(error, "Failed to accept suggestion. Please try again.");
        }
    }, [pushHistory, applyUpdates, setScrollToId]);

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
                { redaction_type: newType, is_accepted: true, is_suggestion: false }
            );
            applySingle(updatedRedaction);
            toast.success("Suggestion type changed and accepted.");
            pushHistory(
                async () => applySingle(await updateRedaction(redactionId, { redaction_type: originalType, is_accepted: originalIsAccepted, is_suggestion: originalIsSuggestion })),
                async () => applySingle(await updateRedaction(redactionId, { redaction_type: newType, is_accepted: true, is_suggestion: false }))
            );
        } catch (error) {
            toastError(error, "Failed to change suggestion type. Please try again.");
        }
    }, [redactions, pushHistory, applySingle, setScrollToId]);

    const handleBulkChangeTypeAndAccept = useCallback(async (ids, newType) => {
        setScrollToId(null);
        const originals = ids.map(id => redactions.find(r => r.id === id)).filter(Boolean);
        try {
            const updates = await Promise.all(
                ids.map(id => updateRedaction(id, { redaction_type: newType, is_accepted: true, is_suggestion: false }))
            );
            applyUpdates(updates);
            toast.success("Suggestions type changed and accepted.");
            pushHistory(
                async () => applyUpdates(await Promise.all(
                    originals.map(o => updateRedaction(o.id, { redaction_type: o.redaction_type, is_accepted: o.is_accepted, is_suggestion: o.is_suggestion }))
                )),
                async () => applyUpdates(await Promise.all(
                    ids.map(id => updateRedaction(id, { redaction_type: newType, is_accepted: true, is_suggestion: false }))
                ))
            );
        } catch (error) {
            toastError(error, "Failed to change suggestion types. Please try again.");
        }
    }, [redactions, pushHistory, applyUpdates, setScrollToId]);

    const handleSplitMerge = useCallback((mergeKey) => {
        setScrollToId(null);
        setSplitMerges(prev => new Set(prev).add(mergeKey));
        pushHistory(
            async () => setSplitMerges(prev => { const n = new Set(prev); n.delete(mergeKey); return n; }),
            async () => setSplitMerges(prev => new Set(prev).add(mergeKey))
        );
    }, [pushHistory, setSplitMerges, setScrollToId]);

    const handleRemoveFromMerge = useCallback((id) => {
        setScrollToId(null);
        setIsolatedIds(prev => new Set(prev).add(id));
        pushHistory(
            async () => setIsolatedIds(prev => { const n = new Set(prev); n.delete(id); return n; }),
            async () => setIsolatedIds(prev => new Set(prev).add(id))
        );
    }, [pushHistory, setIsolatedIds, setScrollToId]);

    return {
        handleAcceptSuggestion,
        handleBulkAccept,
        handleReject,
        handleBulkReject,
        handleAcceptWithExemption,
        handleChangeTypeAndAccept,
        handleBulkChangeTypeAndAccept,
        handleSplitMerge,
        handleRemoveFromMerge,
    };
}
