import { useState, useCallback } from 'react';
import { useUndoHistory } from '@/hooks/useUndoHistory';
import { useRedactionDisplay } from '@/hooks/useRedactionDisplay';
import { useDocumentControls } from '@/hooks/useDocumentControls';
import { useRedactionActions } from '@/hooks/useRedactionActions';
import { useRemoveRedaction } from '@/hooks/useRemoveRedaction';
import { useManualRedaction } from '@/hooks/useManualRedaction';
import { useMarkAllInCase } from '@/hooks/useMarkAllInCase';

export function useRedactionState({ document: currentDocument, initialRedactions, router }) {
    const [redactions, setRedactions] = useState(initialRedactions || []);
    const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
    const [rejectionTarget, setRejectionTarget] = useState(null);
    const [bulkRejectIds, setBulkRejectIds] = useState([]);

    const { push: pushHistory, undo, redo, clear: clearHistory, canUndo, canRedo } = useUndoHistory({ maxSize: 25 });

    const {
        displaySections,
        setSplitMerges,
        setIsolatedIds,
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
    } = useDocumentControls({ undo, redo, clearHistory, currentDocument, router });

    const openRejectDialog = useCallback(({ id, text }) => {
        setRejectionTarget({ id, text });
        setRejectionDialogOpen(true);
    }, []);

    const closeRejectDialog = useCallback(() => {
        setRejectionDialogOpen(false);
        setRejectionTarget(null);
    }, []);

    const {
        markAllInCaseTarget,
        setMarkAllInCaseTarget,
        handleMarkAllInCase,
        handleMarkAllInCaseAcceptConfirm,
        handleMarkAllInCaseRejectConfirm,
    } = useMarkAllInCase({
        caseId: currentDocument.case,
        setRedactions,
        openRejectDialog,
        closeRejectDialog,
    });

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
        handleRemoveFromMerge,
    } = useRedactionActions({
        documentId: currentDocument.id,
        redactions,
        setRedactions,
        pushHistory,
        setSplitMerges,
        setIsolatedIds,
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
        redactions,
        setRedactions,
        pushHistory,
        activeHighlightType,
    });

    const handleCloseRejectionDialog = useCallback(() => {
        setRejectionDialogOpen(false);
        setRejectionTarget(null);
        setBulkRejectIds([]);
        setMarkAllInCaseTarget(null);
    }, [setMarkAllInCaseTarget]);

    return {
        redactions,
        displaySections,
        pendingCount: displaySections.pending.total,

        hoveredSuggestionId,
        scrollToId,
        handleSuggestionMouseEnter,
        handleSuggestionMouseLeave,
        handleHighlightClick,
        handleRemoveScrollId,
        handleCardClick,

        manualRedactionAnchor,
        pendingRedaction,
        handleTextSelect,
        handleCreateManualRedaction,
        handleCloseManualRedactionPopover,
        handleOnContextSave,

        handleRemoveRedaction,
        handleRemoveSelect,
        handleUnhighlightClick,

        handleAcceptSuggestion,
        handleBulkAccept,
        handleRejectAsDisclosable,
        handleChangeTypeAndAccept,
        handleBulkChangeTypeAndAccept,
        handleOpenRejectDialog,
        handleOpenBulkRejectDialog,
        handleRejectConfirm,
        handleSplitMerge,
        handleRemoveFromMerge,

        markAllInCaseTarget,
        setMarkAllInCaseTarget,
        handleMarkAllInCase,
        handleMarkAllInCaseAcceptConfirm,
        handleMarkAllInCaseRejectConfirm,

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

        undo,
        redo,
        canUndo,
        canRedo,

        rejectionDialogOpen,
        rejectionTarget,
        handleCloseRejectionDialog,
    };
}
