"use client"

import React, { useState } from 'react';
import { Box, Typography, Button, Container, Tooltip, CircularProgress, IconButton } from '@mui/material';
import TextDecreaseIcon from '@mui/icons-material/TextDecrease';
import TextIncreaseIcon from '@mui/icons-material/TextIncrease';
import RefreshIcon from '@mui/icons-material/Refresh';
import NextLink from 'next/link';
import { RedactionSidebar } from '@/components/RedactionSidebar';
import { ManualRedactionPopover } from '@/components/ManualRedactionPopover';
import { RejectReasonDialog } from '@/components/RejectReasonDialog';
import { ResubmitDialog } from '@/components/ResubmitDialog';
import { DocumentViewer } from '@/components/DocumentViewer';
import { useUndoHistory } from '@/hooks/useUndoHistory';
import { useDocumentControls } from '@/hooks/useDocumentControls';
import { useRedactionDisplay } from '@/hooks/useRedactionDisplay';
import { useRedactionActions } from '@/hooks/useRedactionActions';
import { useRemoveRedaction } from '@/hooks/useRemoveRedaction';
import { useManualRedaction } from '@/hooks/useManualRedaction';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';

export const RedactionComponent = ({ document: currentDocument, initialRedactions }) => {
    const { data: session } = useSession();
    const router = useRouter();
    const [redactions, setRedactions] = useState(initialRedactions || []);

    // State for rejection dialog (single and bulk)
    const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
    const [rejectionTarget, setRejectionTarget] = useState(null);
    const [bulkRejectIds, setBulkRejectIds] = useState([]);

    // Undo/redo history
    const { push: pushHistory, undo, redo, clear: clearHistory, canUndo, canRedo } = useUndoHistory({ maxSize: 25 });

    const {
        displaySections,
        setSplitMerges,
        hoveredSuggestionId,
        scrollToId,
        setScrollToId,
        handleSuggestionMouseEnter,
        handleSuggestionMouseLeave,
        handleHighlightClick,
        handleRemoveScrollId,
        handleCardClick,
    } = useRedactionDisplay({ redactions });

    const {
        isLoading,
        isResubmitting,
        resubmitDialogOpen,
        setResubmitDialogOpen,
        baseFontSize,
        canIncreaseFont,
        canDecreaseFont,
        sidebarWidth,
        activeHighlightType,
        handleToggleHighlightTool,
        handleFontDecrease,
        handleFontIncrease,
        handleResizeStart,
        handleMarkAsComplete,
        handleResubmit,
    } = useDocumentControls({ accessToken: session?.access_token, undo, redo, clearHistory, currentDocument, router });

    const {
        handleAcceptSuggestion,
        handleBulkAccept,
        handleRejectAsDisclosable,
        handleChangeTypeAndAccept,
        handleBulkChangeTypeAndAccept,
        handleOpenRejectDialog,
        handleOpenBulkRejectDialog,
        handleRejectConfirm,
        handleSplitMerge,
    } = useRedactionActions({
        documentId: currentDocument.id,
        accessToken: session?.access_token,
        redactions,
        setRedactions,
        pushHistory,
        setSplitMerges,
        setScrollToId,
        bulkRejectIds,
        setBulkRejectIds,
        setRejectionDialogOpen,
        setRejectionTarget,
    });

    const {
        handleRemoveRedaction,
        handleRemoveSelect,
        handleUnhighlightClick,
    } = useRemoveRedaction({
        documentId: currentDocument.id,
        extractedText: currentDocument.extracted_text,
        accessToken: session?.access_token,
        redactions,
        setRedactions,
        pushHistory,
        displaySections,
    });

    const {
        manualRedactionAnchor,
        pendingRedaction,
        handleTextSelect,
        handleCreateManualRedaction,
        handleCloseManualRedactionPopover,
        handleOnContextSave,
    } = useManualRedaction({
        documentId: currentDocument.id,
        extractedText: currentDocument.extracted_text,
        accessToken: session?.access_token,
        redactions,
        setRedactions,
        pushHistory,
        activeHighlightType,
    });

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
                                    disabled={!canDecreaseFont}
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
                                    disabled={!canIncreaseFont}
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
                    onRemoveSelect={handleRemoveSelect}
                    onHighlightClick={handleHighlightClick}
                    onUnhighlightClick={handleUnhighlightClick}
                    reviewComplete={pendingCount === 0}
                    baseFontSize={baseFontSize}
                    activeHighlightType={activeHighlightType}
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
                    onCardClick={handleCardClick}
                    activeHighlightType={activeHighlightType}
                    onToggleHighlightTool={handleToggleHighlightTool}
                    documentCompleted={currentDocument.status === 'Completed'}
                    onUndo={undo}
                    onRedo={redo}
                    canUndo={canUndo}
                    canRedo={canRedo}
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

            <ResubmitDialog
                open={resubmitDialogOpen}
                onClose={() => setResubmitDialogOpen(false)}
                onConfirm={handleResubmit}
                isConfirming={isResubmitting}
            />
        </Box>
    );
}
