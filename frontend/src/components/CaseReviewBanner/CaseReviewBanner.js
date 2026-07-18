"use client";

import React, { useState } from 'react';
import { Alert, AlertTitle, Button } from '@mui/material';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import toast from 'react-hot-toast';

import { openCaseReview } from '@/services/caseService';

/**
 * Surfaces the post-disclosure review state of a case:
 *
 * - While a review is open (case status UNDER_REVIEW) it shows an "unlocked"
 *   banner so the reviewer knows redaction edits are permitted and tracked.
 * - Once a case is disclosed but not under review it offers an "Open Review"
 *   action, the sanctioned way to unlock the disclosed decisions again.
 *
 * Renders nothing for cases that have never been disclosed.
 */
export const CaseReviewBanner = ({ caseData, onUpdate }) => {
    const [isOpening, setIsOpening] = useState(false);

    const isUnderReview = caseData?.status === 'UNDER_REVIEW';
    const isDisclosed = Boolean(caseData?.is_disclosed);

    const handleOpenReview = async () => {
        setIsOpening(true);
        try {
            await openCaseReview(caseData.id);
            toast.success('Internal review opened. Redactions are now editable.', {
                id: 'review-toast',
            });
            if (onUpdate) await onUpdate();
        } catch (error) {
            toast.error('Failed to open the review.', { id: 'review-toast' });
        } finally {
            setIsOpening(false);
        }
    };

    if (isUnderReview) {
        return (
            <Alert severity="warning" icon={<LockOpenIcon fontSize="inherit" />}>
                <AlertTitle>Under internal review — unlocked</AlertTitle>
                This case has been disclosed and is currently under review.
                Redaction changes are permitted and are being tracked against
                this review.
            </Alert>
        );
    }

    if (!isDisclosed) {
        return null;
    }

    return (
        <Alert
            severity="info"
            action={
                <Button
                    color="inherit"
                    size="small"
                    startIcon={<LockOpenIcon />}
                    onClick={handleOpenReview}
                    loading={isOpening}
                >
                    Open Review
                </Button>
            }
        >
            <AlertTitle>Disclosed &amp; locked</AlertTitle>
            This case has been disclosed. Open an internal review to change its
            redactions and re-disclose.
        </Alert>
    );
};
