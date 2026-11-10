import { useState, useCallback } from 'react';
import { bulkMarkByText } from '@/services/redactionService';
import toast from 'react-hot-toast';
import { toastError } from '@/api/toastError';
import { isPendingSuggestion } from '@/utils/redactionDecision';

/**
 * Manages case-wide accept/reject for a specific text+redaction_type pair.
 *
 * Both actions change every document in the case, so each waits for the
 * parent's confirmation dialog: handleMarkAllInCase sets the target, and the
 * matching confirm handler applies it. A rejection carries no reason.
 */
export function useMarkAllInCase({ caseId, setRedactions }) {
    const [markAllInCaseTarget, setMarkAllInCaseTarget] = useState(null);

    const handleMarkAllInCase = useCallback(({ text, redactionType, action }) => {
        setMarkAllInCaseTarget({ text, redactionType, action });
    }, []);

    const handleMarkAllInCaseAcceptConfirm = useCallback(async () => {
        const { text, redactionType } = markAllInCaseTarget;
        setMarkAllInCaseTarget(null);
        try {
            const { updated } = await bulkMarkByText(caseId, text, redactionType, 'ACCEPTED', null);
            setRedactions(prev =>
                prev.map(r =>
                    isPendingSuggestion(r) &&
                    r.text === text && r.redaction_type === redactionType
                        ? { ...r, is_accepted: true, decided_by: 'HUMAN' }
                        : r
                )
            );
            toast.success(`Accepted ${updated} redaction${updated !== 1 ? 's' : ''} across this case.`);
        } catch (error) {
            toastError(error, 'Failed to mark all in case. Please try again.');
        }
    }, [markAllInCaseTarget, caseId, setRedactions]);

    const handleMarkAllInCaseRejectConfirm = useCallback(async () => {
        const { text, redactionType } = markAllInCaseTarget;
        setMarkAllInCaseTarget(null);
        try {
            const { updated } = await bulkMarkByText(caseId, text, redactionType, 'REJECTED', null);
            setRedactions(prev =>
                prev.map(r =>
                    isPendingSuggestion(r) &&
                    r.text === text && r.redaction_type === redactionType
                        ? { ...r, is_accepted: false, decided_by: 'HUMAN' }
                        : r
                )
            );
            toast.success(`Rejected ${updated} redaction${updated !== 1 ? 's' : ''} across this case.`);
        } catch (error) {
            toastError(error, 'Failed to mark all in case. Please try again.');
        }
    }, [markAllInCaseTarget, caseId, setRedactions]);

    return {
        markAllInCaseTarget,
        setMarkAllInCaseTarget,
        handleMarkAllInCase,
        handleMarkAllInCaseAcceptConfirm,
        handleMarkAllInCaseRejectConfirm,
    };
}
