"use client"

import React, { useState, useCallback } from 'react';
import { Box, Typography, Button, Container, Tooltip, CircularProgress, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, IconButton } from '@mui/material';
import TextDecreaseIcon from '@mui/icons-material/TextDecrease';
import TextIncreaseIcon from '@mui/icons-material/TextIncrease';
import RefreshIcon from '@mui/icons-material/Refresh';
import NextLink from 'next/link';
import { RedactionSidebar } from '@/components/RedactionSidebar';
import { ManualRedactionPopover } from '@/components/ManualRedactionPopover';
import { RejectReasonDialog } from '@/components/RejectReasonDialog';
import { DocumentViewer } from '@/components/DocumentViewer';
import { markAsComplete, resubmitDocument } from '@/services/documentService'
import { createRedaction, updateRedaction, deleteRedaction } from '@/services/redactionService';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';

const FONT_SIZE_STEPS = [0.75, 0.85, 1, 1.15, 1.3, 1.5];

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

    // State for resubmit confirmation dialog
    const [resubmitDialogOpen, setResubmitDialogOpen] = useState(false);
    const [isResubmitting, setIsResubmitting] = useState(false);

    // Font size controls
    const [fontSizeIndex, setFontSizeIndex] = useState(2);
    const baseFontSize = FONT_SIZE_STEPS[fontSizeIndex];
    const handleFontDecrease = useCallback(() => setFontSizeIndex(prev => Math.max(0, prev - 1)), []);
    const handleFontIncrease = useCallback(() => setFontSizeIndex(prev => Math.min(FONT_SIZE_STEPS.length - 1, prev + 1)), []);

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

    const handleResubmit = useCallback(async () => {
        setIsResubmitting(true);
        try {
            await resubmitDocument(currentDocument.id, session?.access_token);
            toast.success("Document resubmitted for processing.");
            router.push(`/cases/${currentDocument.case}`);
        } catch (error) {
            toast.error("Failed to resubmit document. Please try again.");
        } finally {
            setIsResubmitting(false);
            setResubmitDialogOpen(false);
        }
    }, [currentDocument.id, currentDocument.case, session?.access_token, router]);


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
        <Box sx={{ display: 'flex', height: 'calc(100vh - 32px)' }}>
            <Container maxWidth={false} sx={{ my: 0, display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, pb: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <Box>
                        <Button component={NextLink} href={`/cases/${currentDocument.case || currentDocument.id}`} variant="contained" color="primary">
                            Back to Case
                        </Button>
                    </Box>
                    <Box>
                        <Typography variant="body1" component="h1">{currentDocument?.filename}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                        <Tooltip title="Decrease font size">
                            <span>
                                <IconButton
                                    aria-label="Decrease font size"
                                    onClick={handleFontDecrease}
                                    disabled={fontSizeIndex === 0}
                                    size="small"
                                    sx={{ fontSize: '0.85rem', fontWeight: 'bold' }}
                                >
                                    <TextDecreaseIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Increase font size">
                            <span>
                                <IconButton
                                    aria-label="Increase font size"
                                    onClick={handleFontIncrease}
                                    disabled={fontSizeIndex === FONT_SIZE_STEPS.length - 1}
                                    size="small"
                                    sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}
                                >
                                    <TextIncreaseIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        {currentDocument.status !== 'Completed' ? (
                            <>
                                <Tooltip title="Resubmit for processing">
                                    <IconButton
                                        aria-label="Resubmit for processing"
                                        color="warning"
                                        onClick={() => setResubmitDialogOpen(true)}
                                        disabled={isResubmitting}
                                    >
                                        <RefreshIcon />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title={pendingSuggestions.length > 0 ? "You must resolve all AI suggestions before completing." : ""}>
                                    <span>
                                        <Button
                                            variant="contained"
                                            color="info"
                                            disabled={pendingSuggestions.length > 0 || isLoading}
                                            onClick={handleMarkAsComplete}
                                            sx={{ minWidth: 180 }}
                                        >
                                            {isLoading ? <CircularProgress size={24} color="inherit" /> : 'Mark as Complete'}
                                        </Button>
                                    </span>
                                </Tooltip>
                            </>
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
                    tables={currentDocument?.extracted_tables}
                    structure={currentDocument?.extracted_structure}
                    redactions={redactions}
                    pendingRedaction={pendingRedaction}
                    hoveredSuggestionId={hoveredSuggestionId}
                    onTextSelect={handleTextSelect}
                    onHighlightClick={handleHighlightClick}
                    reviewComplete={pendingSuggestions.length === 0}
                    baseFontSize={baseFontSize}
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

            <Dialog
                open={resubmitDialogOpen}
                onClose={() => setResubmitDialogOpen(false)}
            >
                <DialogTitle>Resubmit Document</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        This will delete all current redactions (including any manual redactions you have made) and reprocess the document with the current AI model. This action cannot be undone.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setResubmitDialogOpen(false)} disabled={isResubmitting}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleResubmit}
                        color="warning"
                        variant="contained"
                        disabled={isResubmitting}
                    >
                        {isResubmitting ? <CircularProgress size={24} color="inherit" /> : 'Resubmit'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
