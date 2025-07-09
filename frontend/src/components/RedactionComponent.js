"use client"

import React, { useState, useCallback } from 'react';
import { Box, Typography, Button, Container, Tooltip } from '@mui/material';

import RedactionSidebar from './redaction/RedactionSidebar';
import ManualRedactionPopover from './redaction/ManualRedactionPopover';
import RejectReasonDialog from './redaction/RejectReasonDialog';
import DocumentViewer from './redaction/DocumentViewer';

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

    const handleAcceptSuggestion = useCallback((redactionId) => {
        setRedactions(prev => prev.map(r =>
            r.id === redactionId ? { ...r, is_accepted: true, is_suggestion: false } : r
        ));
    }, []);

    const handleOpenRejectDialog = useCallback((redaction) => {
        setRejectionTarget(redaction);
        setRejectionDialogOpen(true);
    }, []);

    const handleRejectSuggestion = useCallback((redactionId, reason) => {
        console.log(`Redaction ${redactionId} rejected. Reason: ${reason}`); // TODO: Send this to the backend
        setRedactions(prev => prev.filter(r => r.id !== redactionId));
        setRejectionDialogOpen(false);
        setRejectionTarget(null);
    }, []);

    const handleRemoveRedaction = useCallback((redactionId) => {
        setRedactions(prev => {
            const redactionToRemove = prev.find(r => r.id === redactionId);
            if (!redactionToRemove) return prev;

            // If it was a user-created redaction, filter it out completely.
            if (!redactionToRemove.is_suggestion) {
                return prev.filter(r => r.id !== redactionId);
            }

            // If it was an AI suggestion that was accepted, revert it to a suggestion.
            return prev.map(r =>
                r.id === redactionId ? { ...r, is_accepted: false } : r
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

    const suggestions = redactions.filter(r => r.is_suggestion && !r.is_accepted);

    return (
        <Box sx={{ display: 'flex', height: 'calc(100vh - 64px)' }}>
            <Container maxWidth={false} sx={{ my: 4, display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, pb: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <Box>
                        <Typography variant="h5" component="h1">{document?.filename}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <Tooltip title={suggestions.length > 0 ? "You must resolve all AI suggestions before completing." : ""}>
                            <span>
                                <Button
                                    variant="contained"
                                    color="primary"
                                    disabled={suggestions.length > 0}
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
                redactions={redactions}
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
