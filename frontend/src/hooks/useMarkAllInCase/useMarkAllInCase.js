import { useState, useCallback } from 'react';
import { bulkMarkByText } from '@/services/redactionService';
import toast from 'react-hot-toast';

/**
 * Manages case-wide accept/reject for a specific text+redaction_type pair.
 *
 * Accepts two callbacks that bridge to the shared rejection dialog:
 *   openRejectDialog(target)  — opens RejectReasonDialog with the given target
 *   closeRejectDialog()       — closes the dialog and clears its target
 *
 * The parent must still own rejectionDialogOpen / rejectionTarget state because
 * that dialog is also shared with per-document reject actions.
 */
export function useMarkAllInCase({ caseId, setRedactions, openRejectDialog, closeRejectDialog }) {
    const [markAllInCaseTarget, setMarkAllInCaseTarget] = useState(null);

    const handleMarkAllInCase = useCallback(({ text, redactionType, action }) => {
        setMarkAllInCaseTarget({ text, redactionType, action });
        if (action === 'reject') {
            openRejectDialog({ id: null, text });
        }
    }, [openRejectDialog]);

    const handleMarkAllInCaseAcceptConfirm = useCallback(async () => {
        const { text, redactionType } = markAllInCaseTarget;
        setMarkAllInCaseTarget(null);
        try {
            const { updated } = await bulkMarkByText(caseId, text, redactionType, 'ACCEPTED', null);
            setRedactions(prev =>
                prev.map(r =>
                    r.is_suggestion && !r.is_accepted && !r.justification &&
                    r.text === text && r.redaction_type === redactionType
                        ? { ...r, is_accepted: true }
                        : r
                )
            );
            toast.success(`Accepted ${updated} redaction${updated !== 1 ? 's' : ''} across this case.`);
        } catch {
            toast.error('Failed to mark all in case. Please try again.');
        }
    }, [markAllInCaseTarget, caseId, setRedactions]);

    const handleMarkAllInCaseRejectConfirm = useCallback(async (_id, reason) => {
        const { text, redactionType } = markAllInCaseTarget;
        closeRejectDialog();
        setMarkAllInCaseTarget(null);
        try {
            const { updated } = await bulkMarkByText(caseId, text, redactionType, 'REJECTED', reason);
            setRedactions(prev =>
                prev.map(r =>
                    r.is_suggestion && !r.is_accepted && !r.justification &&
                    r.text === text && r.redaction_type === redactionType
                        ? { ...r, justification: reason }
                        : r
                )
            );
            toast.success(`Rejected ${updated} redaction${updated !== 1 ? 's' : ''} across this case.`);
        } catch {
            toast.error('Failed to mark all in case. Please try again.');
        }
    }, [markAllInCaseTarget, caseId, setRedactions, closeRejectDialog]);

    return {
        markAllInCaseTarget,
        setMarkAllInCaseTarget,
        handleMarkAllInCase,
        handleMarkAllInCaseAcceptConfirm,
        handleMarkAllInCaseRejectConfirm,
    };
}
