"use client"

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
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
import { createRedaction, updateRedaction, deleteRedaction, bulkUpdateRedactions, getExemptionTemplates } from '@/services/redactionService';
import { mergeAdjacentSpans, groupByTextAndType } from '@/utils/mergeRedactionSpans';
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

    // State for rejection dialog (single and bulk)
    const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
    const [rejectionTarget, setRejectionTarget] = useState(null);
    const [bulkRejectIds, setBulkRejectIds] = useState([]);

    // State for hovering suggestions
    const [hoveredSuggestionId, setHoveredSuggestionId] = useState(null);

    // State to trigger scroll-to-view in the sidebar
    const [scrollToId, setScrollToId] = useState(null);

    // State for resubmit confirmation dialog
    const [resubmitDialogOpen, setResubmitDialogOpen] = useState(false);
    const [isResubmitting, setIsResubmitting] = useState(false);

    // Exemption templates for the reject dropdown
    const [exemptionTemplates, setExemptionTemplates] = useState([]);

    useEffect(() => {
        if (!session?.access_token) return;
        getExemptionTemplates(session.access_token)
            .then(setExemptionTemplates)
            .catch(() => {});
    }, [session?.access_token]);

    // State for merged span splits (display-only)
    const [splitMerges, setSplitMerges] = useState(new Set());

    // Font size controls
    const [fontSizeIndex, setFontSizeIndex] = useState(2);
    const baseFontSize = FONT_SIZE_STEPS[fontSizeIndex];
    const handleFontDecrease = useCallback(() => setFontSizeIndex(prev => Math.max(0, prev - 1)), []);
    const handleFontIncrease = useCallback(() => setFontSizeIndex(prev => Math.min(FONT_SIZE_STEPS.length - 1, prev + 1)), []);

    // Sidebar resize controls
    const [sidebarWidth, setSidebarWidth] = useState(() => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('sidebarWidth');
            return saved ? parseInt(saved, 10) : 450;
        }
        return 450;
    });
    const isResizing = useRef(false);

    const handleResizeStart = useCallback((e) => {
        e.preventDefault();
        isResizing.current = true;
        const doc = e.target.ownerDocument;

        const handleResize = (e) => {
            if (!isResizing.current) return;
            const newWidth = doc.defaultView.innerWidth - e.clientX;
            const maxWidth = doc.defaultView.innerWidth * 0.6;
            const clamped = Math.min(maxWidth, Math.max(250, newWidth));
            setSidebarWidth(clamped);
            localStorage.setItem('sidebarWidth', String(Math.round(clamped)));
        };

        const handleResizeEnd = () => {
            isResizing.current = false;
            doc.removeEventListener('mousemove', handleResize);
            doc.removeEventListener('mouseup', handleResizeEnd);
        };

        doc.addEventListener('mousemove', handleResize);
        doc.addEventListener('mouseup', handleResizeEnd);
    }, []);

    useEffect(() => {
        return () => {
            isResizing.current = false;
        };
    }, []);

    const handleAcceptSuggestion = useCallback(async (redactionId) => {
        setScrollToId(null);
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

    const handleBulkAccept = useCallback(async (ids) => {
        setScrollToId(null);
        try {
            const updatedRedactions = await bulkUpdateRedactions(
                document.id, ids, true, null, session?.access_token
            );
            setRedactions(prev => {
                const updatedMap = new Map(updatedRedactions.map(r => [r.id, r]));
                return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
            });
        } catch (error) {
            toast.error("Failed to accept suggestions. Please try again.");
        }
    }, [document.id, session?.access_token]);

    const handleRejectAsDisclosable = useCallback(async (ids, justification) => {
        setScrollToId(null);
        try {
            if (ids.length === 1) {
                const updated = await updateRedaction(
                    ids[0], { is_accepted: false, justification }, session?.access_token
                );
                setRedactions(prev => prev.map(r => r.id === ids[0] ? updated : r));
            } else {
                const updatedList = await bulkUpdateRedactions(
                    document.id, ids, false, justification, session?.access_token
                );
                setRedactions(prev => {
                    const updatedMap = new Map(updatedList.map(r => [r.id, r]));
                    return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
                });
            }
        } catch (error) {
            toast.error("Failed to reject suggestion. Please try again.");
        }
    }, [document.id, session?.access_token]);

    const handleChangeTypeAndAccept = useCallback(async (redactionId, newType) => {
        setScrollToId(null);
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

    const handleBulkChangeTypeAndAccept = useCallback(async (ids, newType) => {
        setScrollToId(null);
        try {
            const updates = await Promise.all(
                ids.map(id => updateRedaction(id, { redaction_type: newType, is_accepted: true, is_suggestion: false }, session?.access_token))
            );
            setRedactions(prev => {
                const updatedMap = new Map(updates.map(r => [r.id, r]));
                return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
            });
            toast.success("Suggestions type changed and accepted.");
        } catch (error) {
            toast.error("Failed to change suggestion types. Please try again.");
        }
    }, [session?.access_token]);

    const handleOpenRejectDialog = useCallback((redaction) => {
        setBulkRejectIds([]);
        setRejectionTarget(redaction);
        setRejectionDialogOpen(true);
    }, []);

    const handleOpenBulkRejectDialog = useCallback((ids) => {
        setBulkRejectIds(ids);
        setRejectionTarget({ id: null, text: `${ids.length} selected items` });
        setRejectionDialogOpen(true);
    }, []);

    const handleRejectConfirm = useCallback(async (redactionId, reason) => {
        setScrollToId(null);
        if (bulkRejectIds.length > 0) {
            try {
                const updatedRedactions = await bulkUpdateRedactions(
                    document.id, bulkRejectIds, false, reason, session?.access_token
                );
                setRedactions(prev => {
                    const updatedMap = new Map(updatedRedactions.map(r => [r.id, r]));
                    return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
                });
            } catch (error) {
                toast.error("Failed to reject suggestions. Please try again.");
            } finally {
                setRejectionDialogOpen(false);
                setRejectionTarget(null);
                setBulkRejectIds([]);
            }
        } else {
            try {
                const updatedRedaction = await updateRedaction(
                    redactionId,
                    { is_accepted: false, justification: reason },
                    session?.access_token
                );
                setRedactions(prev => prev.map(r =>
                    r.id === redactionId ? updatedRedaction : r
                ));
            } catch (error) {
                toast.error("Failed to reject suggestion. Please try again.");
            } finally {
                setRejectionDialogOpen(false);
                setRejectionTarget(null);
            }
        }
    }, [bulkRejectIds, document.id, session?.access_token]);

    const handleSplitMerge = useCallback((mergeKey) => {
        setSplitMerges(prev => new Set(prev).add(mergeKey));
    }, []);

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

    const handleTextSelect = useCallback((selection, rect) => {
        setNewSelection(selection);
        setPendingRedaction(selection);
        const virtualEl = { getBoundingClientRect: () => rect, nodeType: 1 };
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

        // Find any existing redactions that overlap with the selection
        const overlapping = redactions.filter(r =>
            r.start_char < newSelection.end_char && r.end_char > newSelection.start_char
        );

        if (overlapping.length > 0) {
            const sameType = overlapping.every(r => r.redaction_type === redactionType);
            if (sameType) {
                // Already redacted with this classification — don't duplicate
                handleCloseManualRedactionPopover();
                toast("This text is already redacted with this classification.");
                return;
            }
            // Different classification — overwrite the existing redaction(s)
            try {
                const updates = await Promise.all(
                    overlapping.map(r => updateRedaction(r.id, { redaction_type: redactionType, is_accepted: true, is_suggestion: false }, session?.access_token))
                );
                setRedactions(prev => {
                    const updatedMap = new Map(updates.map(r => [r.id, r]));
                    return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
                });
                handleCloseManualRedactionPopover();
                toast.success("Redaction classification updated.");
            } catch (error) {
                handleCloseManualRedactionPopover();
                toast.error("Failed to update redaction. Please try again.");
            }
            return;
        }

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

    }, [newSelection, document.id, handleCloseManualRedactionPopover, session?.access_token, redactions]);

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
            const updatedDocument = await markAsComplete(currentDocument.id, session?.access_token);
            console.log(updatedDocument);
            toast.success("Document is ready for disclosure.");
            router.push(`/cases/${currentDocument.case}`);
        } catch (error) {
            toast.error("Failed to mark document as complete. Please try again.");
        } finally {
            setIsLoading(false);
        }
    }, [currentDocument.id, currentDocument.case, session?.access_token, router]);

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

    // Compute grouped/merged display sections for the sidebar
    const displaySections = useMemo(() => {
        const pending = redactions.filter(r => r.is_suggestion && !r.is_accepted && !r.justification);
        const accepted = redactions.filter(r => r.is_suggestion && r.is_accepted);
        const rejected = redactions.filter(r => r.is_suggestion && !r.is_accepted && !!r.justification);
        const manual = redactions.filter(r => !r.is_suggestion);

        const processSection = (items) => ({
            total: items.length,
            items: groupByTextAndType(mergeAdjacentSpans(items, splitMerges)),
        });

        return {
            pending: processSection(pending),
            accepted: processSection(accepted),
            rejected: processSection(rejected),
            manual: processSection(manual),
        };
    }, [redactions, splitMerges]);

    const pendingCount = displaySections.pending.total;

    return (
        <Box sx={{ display: 'flex', height: 'calc(100vh - 32px)' }}>
            <Container maxWidth={false} sx={{ my: 0, display: 'flex', flexDirection: 'column', flexGrow: 1, overflowY: 'auto' }}>
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
                                <Tooltip title={pendingCount > 0 ? "You must resolve all AI suggestions before completing." : ""}>
                                    <span>
                                        <Button
                                            variant="contained"
                                            color="info"
                                            disabled={pendingCount > 0 || isLoading}
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
                    reviewComplete={pendingCount === 0}
                    baseFontSize={baseFontSize}
                />
            </Container>

            <Box
                data-testid="resize-handle"
                onMouseDown={handleResizeStart}
                sx={{
                    width: '6px',
                    cursor: 'col-resize',
                    backgroundColor: 'divider',
                    '&:hover': { backgroundColor: 'primary.main' },
                    flexShrink: 0,
                }}
            />
            <Box sx={{ width: sidebarWidth, flexShrink: 0 }}>
                <RedactionSidebar
                    redactions={displaySections}
                    onAccept={handleAcceptSuggestion}
                    onReject={handleOpenRejectDialog}
                    onRemove={handleRemoveRedaction}
                    onChangeTypeAndAccept={handleChangeTypeAndAccept}
                    onBulkChangeTypeAndAccept={handleBulkChangeTypeAndAccept}
                    onBulkAccept={handleBulkAccept}
                    onBulkReject={handleOpenBulkRejectDialog}
                    onRejectAsDisclosable={handleRejectAsDisclosable}
                    onSplitMerge={handleSplitMerge}
                    onSuggestionMouseEnter={handleSuggestionMouseEnter}
                    onSuggestionMouseLeave={handleSuggestionMouseLeave}
                    scrollToId={scrollToId}
                    removeScrollId={handleRemoveScrollId}
                    onContextSave={handleOnContextSave}
                    exemptionTemplates={exemptionTemplates}
                />
            </Box>

            <ManualRedactionPopover
                anchorEl={manualRedactionAnchor}
                onClose={handleCloseManualRedactionPopover}
                onRedact={handleCreateManualRedaction}
            />

            {rejectionTarget && (
                <RejectReasonDialog
                    open={rejectionDialogOpen}
                    onClose={() => {
                        setRejectionDialogOpen(false);
                        setRejectionTarget(null);
                        setBulkRejectIds([]);
                    }}
                    onSubmit={handleRejectConfirm}
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
