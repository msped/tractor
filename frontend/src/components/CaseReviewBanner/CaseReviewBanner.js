"use client";

import React, { useState } from 'react';
import {
    Alert,
    AlertTitle,
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    TextField,
} from '@mui/material';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import toast from 'react-hot-toast';

import {
    abandonCaseReview,
    completeCaseReview,
    openCaseReview,
} from '@/services/caseService';

/**
 * Surfaces the post-disclosure review state of a case:
 *
 * - While a review is open (case status UNDER_REVIEW) it shows an "unlocked"
 *   banner and offers the two ways to close the review — Complete (re-export
 *   the amended disclosure) or Abandon (discard the edits) — each requiring a
 *   written outcome captured in a dialog.
 * - Once a case is disclosed but not under review it offers an "Open Review"
 *   action, the sanctioned way to unlock the disclosed decisions again.
 *
 * Renders nothing for cases that have never been disclosed.
 */
export const CaseReviewBanner = ({ caseData, onUpdate }) => {
    const [isOpening, setIsOpening] = useState(false);
    const [closeAction, setCloseAction] = useState(null); // 'complete' | 'abandon'
    const [outcome, setOutcome] = useState('');
    const [isClosing, setIsClosing] = useState(false);

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

    const startClose = (action) => {
        setCloseAction(action);
        setOutcome('');
    };

    const cancelClose = () => {
        setCloseAction(null);
        setOutcome('');
    };

    const handleCloseConfirm = async () => {
        const action = closeAction;
        setIsClosing(true);
        try {
            if (action === 'complete') {
                await completeCaseReview(caseData.id, outcome);
                toast.success('Review completed. A new disclosure is being generated.', {
                    id: 'review-toast',
                });
            } else {
                await abandonCaseReview(caseData.id, outcome);
                toast.success('Review abandoned. The original disclosure stands.', {
                    id: 'review-toast',
                });
            }
            setCloseAction(null);
            setOutcome('');
            if (onUpdate) await onUpdate();
        } catch (error) {
            toast.error(`Failed to ${action} the review.`, { id: 'review-toast' });
        } finally {
            setIsClosing(false);
        }
    };

    if (isUnderReview) {
        const isComplete = closeAction === 'complete';
        return (
            <>
                <Alert severity="warning" icon={<LockOpenIcon fontSize="inherit" />}>
                    <AlertTitle>Under internal review — unlocked</AlertTitle>
                    This case has been disclosed and is currently under review.
                    Redaction changes are permitted and are being tracked against
                    this review.
                    <Box sx={{ mt: 1.5, display: 'flex', gap: 1 }}>
                        <Button
                            color="inherit"
                            size="small"
                            variant="outlined"
                            onClick={() => startClose('complete')}
                        >
                            Complete Review
                        </Button>
                        <Button
                            color="inherit"
                            size="small"
                            variant="outlined"
                            onClick={() => startClose('abandon')}
                        >
                            Abandon Review
                        </Button>
                    </Box>
                </Alert>
                <Dialog
                    open={closeAction !== null}
                    onClose={cancelClose}
                    fullWidth
                    maxWidth="sm"
                >
                    <DialogTitle>
                        {isComplete ? 'Complete review' : 'Abandon review'}
                    </DialogTitle>
                    <DialogContent>
                        <DialogContentText sx={{ mb: 2 }}>
                            {isComplete
                                ? 'Completing regenerates the disclosure package to reflect the current redactions. Record the outcome of this review.'
                                : 'Abandoning discards any changes made during this review and restores the original disclosure. Record the outcome of this review.'}
                        </DialogContentText>
                        <TextField
                            id="review-outcome"
                            autoFocus
                            margin="dense"
                            label="Outcome"
                            fullWidth
                            multiline
                            rows={3}
                            variant="outlined"
                            value={outcome}
                            onChange={(e) => setOutcome(e.target.value)}
                        />
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={cancelClose}>Cancel</Button>
                        <Button
                            onClick={handleCloseConfirm}
                            variant="contained"
                            color={isComplete ? 'primary' : 'error'}
                            disabled={!outcome.trim()}
                            loading={isClosing}
                        >
                            {isComplete ? 'Complete' : 'Abandon'}
                        </Button>
                    </DialogActions>
                </Dialog>
            </>
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
