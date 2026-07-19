import { useState, useCallback } from 'react';
import { previewDsInfoPropagation, applyDsInfoPropagation } from '@/services/redactionService';
import toast from 'react-hot-toast';

/**
 * Drives the DS_INFO propagation preview → confirm → apply flow used during an
 * Internal Review.
 *
 * Outside a review (`active` false) this is inert: the backend still propagates
 * automatically, so `requestPreview` no-ops. During a review the backend
 * suppresses automatic propagation; the reviewer previews the affected
 * documents here and confirms before anything is written.
 */
export function useDsInfoPropagation({ active }) {
    const [preview, setPreview] = useState(null);
    const [redactionId, setRedactionId] = useState(null);
    const [applying, setApplying] = useState(false);

    const requestPreview = useCallback(async (id) => {
        if (!active || !id) return;
        try {
            const data = await previewDsInfoPropagation(id);
            if (data?.affected_documents?.length > 0) {
                setPreview(data);
                setRedactionId(id);
            }
        } catch {
            // Preview is best-effort — if it fails the reviewer simply is not
            // prompted, and no propagation is written.
        }
    }, [active]);

    const cancel = useCallback(() => {
        setPreview(null);
        setRedactionId(null);
    }, []);

    const confirm = useCallback(async () => {
        if (!redactionId) return;
        setApplying(true);
        try {
            const result = await applyDsInfoPropagation(redactionId);
            const total = result?.total_matches ?? 0;
            toast.success(`Propagated to ${total} ${total === 1 ? 'occurrence' : 'occurrences'} across the case.`);
            setPreview(null);
            setRedactionId(null);
        } catch {
            toast.error('Failed to apply propagation. Please try again.');
        } finally {
            setApplying(false);
        }
    }, [redactionId]);

    return {
        propagationPreview: preview,
        propagationDialogOpen: preview !== null,
        propagationApplying: applying,
        requestPropagationPreview: requestPreview,
        confirmPropagation: confirm,
        cancelPropagation: cancel,
    };
}
