"use client"

import React, { useState, useCallback } from 'react';
import { Box, Typography, Button, Container, Tooltip } from '@mui/material';

import RedactionSidebar from './redaction/RedactionSidebar';
import ManualRedactionPopover from './redaction/ManualRedactionPopover';
import RejectReasonDialog from './redaction/RejectReasonDialog';
import DocumentViewer from './redaction/DocumentViewer';
import { updateRedaction } from '@/services/redactionService';

export default function RedactionReviewPage({ document, initialRedactions }) {
    const [redactions, setRedactions] = useState(initialRedactions || []);

    // State for manual redaction popover
    const [manualRedactionAnchor, setManualRedactionAnchor] = useState(null);
    const [newSelection, setNewSelection] = useState(null);

    // State for highlighting text for manual redaction
    const [pendingRedaction, setPendingRedaction] = useState(null);

    // State for rejection dialog
    const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
    const [rejectionTarget, setRejectionTarget] = useState(null);

    // State for hovering suggestions
    const [hoveredSuggestionId, setHoveredSuggestionId] = useState(null);

    const handleAcceptSuggestion = useCallback(async (redactionId) => {
        try {
            const response = await updateRedaction(redactionId, { is_accepted: true });
            const updatedRedaction = response.data;
            setRedactions(prev => prev.map(r =>
                r.id === redactionId ? updatedRedaction : r
            ));
        } catch (error) {
            console.error("Failed to accept suggestion:", error);
            // TODO: react-hot-toast error handling
        }
    }, []);

    const handleOpenRejectDialog = useCallback((redaction) => {
        setRejectionTarget(redaction);
        setRejectionDialogOpen(true);
    }, []);

    const handleRejectSuggestion = useCallback(async (redactionId, reason) => {
        try {
            const response = await updateRedaction(redactionId, { is_accepted: false, justification: reason });
            const updatedRedaction = response.data;
            setRedactions(prev => prev.map(r =>
                r.id === redactionId ? updatedRedaction : r
            ));
            setRejectionDialogOpen(false);
            setRejectionTarget(null);
        } catch(error) {
            console.error("Failed to reject suggestion:", error);
            // TODO: react-hot-toast error handling
        };
    }, []);

    const handleRemoveRedaction = useCallback((redactionId) => {
        setRedactions(prev => {
            const redactionToRemove = prev.find(r => r.id === redactionId);
            if (!redactionToRemove) return prev;

            // If it was a user-created redaction, filter it out completely.
            if (!redactionToRemove.is_suggestion) {
                return prev.filter(r => r.id !== redactionId);
            }

            // If it was an AI suggestion (accepted or rejected), revert it to a pending suggestion.
            return prev.map(r =>
                r.id === redactionId ? { ...r, is_accepted: false, justification: null } : r
            );
        });
    }, []);

    const handleTextSelect = useCallback((selection, range) => {
        setNewSelection(selection);
        setPendingRedaction(selection);
        const virtualEl = { getBoundingClientRect: () => range.getBoundingClientRect(), nodeType: 1 };
        setManualRedactionAnchor(virtualEl);
    }, []);

    const handleCloseManualRedactionPopover = useCallback(() => {
        setManualRedactionAnchor(null);
        setNewSelection(null);
        setPendingRedaction(null);
    }, []);

    const handleCreateManualRedaction = useCallback((redactionType) => {
        if (!newSelection) return;
        const newRedaction = {
            id: `manual-${Date.now()}`,
            ...newSelection,
            redaction_type: redactionType,
            is_suggestion: false,
            is_accepted: true,
        };
        setRedactions(prev => [...prev, newRedaction]);
        handleCloseManualRedactionPopover();
    }, [newSelection, handleCloseManualRedactionPopover]);

    const handleSuggestionMouseEnter = useCallback((suggestionId) => {
        setHoveredSuggestionId(suggestionId);
    }, []);

    const handleSuggestionMouseLeave = useCallback(() => {
        setHoveredSuggestionId(null);
    }, []);

    const pendingSuggestions = redactions.filter(r => r.is_suggestion && !r.is_accepted && !r.justification);
    const manualRedactions = redactions.filter(r => !r.is_suggestion);
    const acceptedSuggestions = redactions.filter(r => r.is_suggestion && r.is_accepted);
    const rejectedSuggestions = redactions.filter(r => r.is_suggestion && !r.is_accepted && !!r.justification);


    const sortedRedactions = {
        pending: pendingSuggestions,
        manual: manualRedactions,
        accepted: acceptedSuggestions,
        rejected: rejectedSuggestions,
    }

    return (
        <Box sx={{ display: 'flex', height: 'calc(100vh - 64px)' }}>
            <Container maxWidth={false} sx={{ my: 4, display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, pb: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <Box>
                        <Typography variant="h5" component="h1">{document?.filename}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <Tooltip title={pendingSuggestions.length > 0 ? "You must resolve all AI suggestions before completing." : ""}>
                            <span>
                                <Button
                                    variant="contained"
                                    color="primary"
                                    disabled={pendingSuggestions.length > 0}
                                    sx={{
                                        // Explicitly set styles for the disabled state for better visibility
                                        '&.Mui-disabled': {
                                            backgroundColor: 'rgba(255, 255, 255, 0.12)',
                                            color: 'rgba(255, 255, 255, 0.5)',
                                        },
                                    }}
                                >
                                    Mark as Complete
                                </Button>
                            </span>
                        </Tooltip>
                    </Box>
                </Box>
                <DocumentViewer
                    text={document?.extracted_text}
                    redactions={redactions}
                    pendingRedaction={pendingRedaction}
                    hoveredSuggestionId={hoveredSuggestionId}
                    onTextSelect={handleTextSelect}
                />
            </Container>

            <RedactionSidebar
                redactions={sortedRedactions}
                onAccept={handleAcceptSuggestion}
                onReject={handleOpenRejectDialog}
                onRemove={handleRemoveRedaction}
                onSuggestionMouseEnter={handleSuggestionMouseEnter}
                onSuggestionMouseLeave={handleSuggestionMouseLeave}
            />

            <ManualRedactionPopover
                anchorEl={manualRedactionAnchor}
                onClose={handleCloseManualRedactionPopover}
                onRedact={handleCreateManualRedaction}
            />

            {rejectionTarget && (
                <RejectReasonDialog
                    open={rejectionDialogOpen}
                    onClose={() => setRejectionDialogOpen(false)}
                    onSubmit={handleRejectSuggestion}
                    redaction={rejectionTarget}
                />
            )}
        </Box>
    );
}
