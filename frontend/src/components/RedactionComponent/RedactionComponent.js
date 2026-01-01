"use client"

import React, { useState, useCallback } from 'react';
import { Box, Typography, Button, Container, Tooltip, CircularProgress } from '@mui/material';
import NextLink from 'next/link';
import { RedactionSidebar } from '@/components/RedactionSidebar';
import { ManualRedactionPopover } from '@/components/ManualRedactionPopover';
import { RejectReasonDialog } from '@/components/RejectReasonDialog';
import { DocumentViewer } from '@/components/DocumentViewer';
import { markAsComplete } from '@/services/documentService'
import { createRedaction, updateRedaction, deleteRedaction } from '@/services/redactionService';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';

export const RedactionComponent = ({ document, initialRedactions }) => {
    const { data: session } = useSession();
    const router = useRouter();
    const [redactions, setRedactions] = useState(initialRedactions || []);
    const [currentDocument, setCurrentDocument] = useState(document);
    const [isLoading, setIsLoading] = useState(false);

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

    // State to trigger scroll-to-view in the sidebar
    const [scrollToId, setScrollToId] = useState(null);

    const handleAcceptSuggestion = useCallback(async (redactionId) => {
        try {
            const updatedRedaction = await updateRedaction(
                redactionId, { is_accepted: true },
                session?.access_token
            );
            setRedactions(prev => prev.map(r =>
                r.id === redactionId ? updatedRedaction : r
            ));
        } catch (error) {
            toast.error("Failed to accept suggestion. Please try again.");
        }
    }, [session?.access_token]);

    const handleChangeTypeAndAccept = useCallback(async (redactionId, newType) => {
        try {
            const updatedRedaction = await updateRedaction(
                redactionId, 
                {
                    redaction_type: newType,
                    is_accepted: true,
                    is_suggestion: false   
                }, session?.access_token
            );
            setRedactions(prev => prev.map(r =>
                r.id === redactionId ? updatedRedaction : r
            ));
            toast.success("Suggestion type changed and accepted.");
        } catch (error) {
            toast.error("Failed to change suggestion type. Please try again.");
        }
    }, [session?.access_token]);

    const handleOpenRejectDialog = useCallback((redaction) => {
        setRejectionTarget(redaction);
        setRejectionDialogOpen(true);
    }, []);

    const handleRejectSuggestion = useCallback(async (redactionId, reason) => {
        try {
            const updatedRedaction = await updateRedaction(
                redactionId, 
                { is_accepted: false, justification: reason },
                session?.access_token
            );
            setRedactions(prev => prev.map(r =>
                r.id === redactionId ? updatedRedaction : r
            ));
            setRejectionDialogOpen(false);
            setRejectionTarget(null);
        } catch(error) {
            toast.error("Failed to reject suggestion. Please try again.");
        };
    }, [session?.access_token]);

    const handleRemoveRedaction = useCallback(async (redactionId) => {
        const redactionToRemove = redactions.find(r => r.id === redactionId);
        if (!redactionToRemove) return;

        // If it was a user-created redaction, delete it from the server.
        if (!redactionToRemove.is_suggestion) {
            try {
                await deleteRedaction(redactionId, session?.access_token);
                setRedactions(prev => prev.filter(r => r.id !== redactionId));
                toast.success("Redaction deleted.");
            } catch (error) {
                toast.error("Failed to delete redaction. Please try again.");
            }
            return;
        }

        // If it was an AI suggestion (accepted or rejected), revert it to a pending suggestion.
        try {
            const updatedRedaction = await updateRedaction(
                redactionId,
                { is_accepted: false, justification: null },
                session?.access_token
            );
            setRedactions(prev => prev.map(r =>
                r.id === redactionId ? updatedRedaction : r
            ));
            toast.success("Suggestion reverted to pending.");
        } catch (error) {
            toast.error("Failed to revert suggestion. Please try again.");
        }
    }, [redactions, session?.access_token]);

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

    const handleOnContextSave = useCallback((redactionId, newContextText) => {
        setRedactions(prevRedactions =>
            prevRedactions.map(r => {
                if (r.id === redactionId) {
                    return { ...r, context: newContextText ? { text: newContextText } : null };
                }
                return r;
            })
        );
    }, []);

    const handleCreateManualRedaction = useCallback(async (redactionType) => {
        if (!newSelection) return;
        const newRedaction = {
            ...newSelection,
            document: document.id,
            redaction_type: redactionType,
            is_suggestion: false,
            is_accepted: true,
        };
        try {
            const createdRedaction = await createRedaction(document.id, newRedaction, session?.access_token);
            setRedactions(prev => [...prev, createdRedaction]);
            handleCloseManualRedactionPopover();
            toast.success("Redaction created successfully.");
            
        } catch (error) {
            handleCloseManualRedactionPopover();
            toast.error("Failed to create redaction. Please try again.");
        }
        
    }, [newSelection, document.id, handleCloseManualRedactionPopover, session?.access_token]);

    const handleSuggestionMouseEnter = useCallback((suggestionId) => {
        setHoveredSuggestionId(suggestionId);
    }, []);

    const handleSuggestionMouseLeave = useCallback(() => {
        setHoveredSuggestionId(null);
    }, []);

    const handleHighlightClick = useCallback((redactionId) => {
        setScrollToId(redactionId);
    }, []);

    const handleRemoveScrollId = useCallback(() => {
        setScrollToId(null);
    }, []);

    const handleMarkAsComplete = useCallback(async () => {
        setIsLoading(true);
        try {
            const updatedDocument =  await markAsComplete(currentDocument.id, session?.access_token);
            console.log(updatedDocument);
            toast.success("Document is ready for disclosure.");
            router.push(`/cases/${currentDocument.case}`);
        } catch (error) {
            toast.error("Failed to mark document as complete. Please try again.");
        } finally {
            setIsLoading(false);
        }
    }, [ currentDocument.id, currentDocument.case, session?.access_token, router]);


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
                        <Button component={NextLink} href={`/cases/${currentDocument.case || currentDocument.id}`} variant="contained" color="primary">
                            Back to Case
                        </Button>
                    </Box>
                    <Box>
                        <Typography variant="h5" component="h1">{currentDocument?.filename}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2 }}>
                        {currentDocument.status !== 'Completed' ? (
                            <Tooltip title={pendingSuggestions.length > 0 ? "You must resolve all AI suggestions before completing." : ""}>
                                <span>
                                    <Button
                                        variant="contained"
                                        color="info"
                                        disabled={pendingSuggestions.length > 0 || isLoading}
                                        onClick={handleMarkAsComplete}
                                        sx={{
                                            minWidth: 180,
                                            '&.Mui-disabled': {
                                                backgroundColor: 'rgba(255, 255, 255, 0.12)',
                                                color: 'rgba(255, 255, 255, 0.5)',
                                            },
                                        }}
                                    >
                                        {isLoading ? <CircularProgress size={24} color="inherit" /> : 'Mark as Complete'}
                                    </Button>
                                </span>
                            </Tooltip>
                        ) : (
                            <Button
                                variant="contained"
                                color="success"
                                sx={{ minWidth: 180 }}
                            >
                                Ready for Disclosure
                            </Button>
                        )}
                    </Box>
                </Box>
                <DocumentViewer
                    text={currentDocument?.extracted_text}
                    redactions={redactions}
                    pendingRedaction={pendingRedaction}
                    hoveredSuggestionId={hoveredSuggestionId}
                    onTextSelect={handleTextSelect}
                    onHighlightClick={handleHighlightClick}
                    reviewComplete={pendingSuggestions.length === 0}
                />
            </Container>

            <RedactionSidebar
                redactions={sortedRedactions}
                onAccept={handleAcceptSuggestion}
                onReject={handleOpenRejectDialog}
                onRemove={handleRemoveRedaction}
                onChangeTypeAndAccept={handleChangeTypeAndAccept}
                onSuggestionMouseEnter={handleSuggestionMouseEnter}
                onSuggestionMouseLeave={handleSuggestionMouseLeave}
                scrollToId={scrollToId}
                removeScrollId={handleRemoveScrollId}
                onContextSave={handleOnContextSave}
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
