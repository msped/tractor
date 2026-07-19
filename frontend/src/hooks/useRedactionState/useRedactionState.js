import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { getMergeStructure } from '@/services/redactionService';
import { useUndoHistory } from '@/hooks/useUndoHistory';
import { useRedactionDisplay } from '@/hooks/useRedactionDisplay';
import { useDocumentControls } from '@/hooks/useDocumentControls';
import { useRedactionActions } from '@/hooks/useRedactionActions';
import { useRemoveRedaction } from '@/hooks/useRemoveRedaction';
import { useManualRedaction } from '@/hooks/useManualRedaction';
import { useMarkAllInCase } from '@/hooks/useMarkAllInCase';
import { useDsInfoPropagation } from '@/hooks/useDsInfoPropagation';

export function useRedactionState({ document: currentDocument, initialRedactions, router }) {
    const [redactions, setRedactions] = useState(initialRedactions || []);
    const [mergePairs, setMergePairs] = useState(currentDocument?.merge_structure?.pairs || []);
    const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
    const [rejectionTarget, setRejectionTarget] = useState(null);
    const [bulkRejectIds, setBulkRejectIds] = useState([]);

    // Merge pairs depend only on span geometry (positions + types), so
    // accept/reject decisions never require a fetch. When geometry changes
    // (manual create, delete, trim, split, undo/redo of those), revalidate
    // the server-computed pairs in the background; until it lands, new spans
    // simply render unmerged.
    const geometryKey = useMemo(
        () => redactions.map(r => `${r.id}:${r.start_char}:${r.end_char}`).sort().join('|'),
        [redactions]
    );
    const lastGeometryKey = useRef(geometryKey);
    useEffect(() => {
        if (geometryKey === lastGeometryKey.current) return;
        lastGeometryKey.current = geometryKey;
        const timer = setTimeout(async () => {
            try {
                const structure = await getMergeStructure(currentDocument.id);
                setMergePairs(structure?.pairs || []);
            } catch {
                // Keep the last known pairs; a failed background revalidate
                // only delays merge display for changed spans.
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [geometryKey, currentDocument.id]);

    const { push: pushHistory, undo, redo, clear: clearHistory, canUndo, canRedo } = useUndoHistory({ maxSize: 25 });

    // During an Internal Review, marking text DS_INFO no longer auto-propagates
    // across the case — the reviewer previews and confirms first.
    const reviewActive = Boolean(currentDocument?.active_review);
    const propagation = useDsInfoPropagation({ active: reviewActive });

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
    } = useRedactionDisplay({ redactions, mergePairs });

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
        onDsInfoCreate: propagation.requestPropagationPreview,
    });

    // Wrap the reclassify actions so that turning a redaction into DS_INFO
    // during a review offers the propagation preview once the write lands.
    const changeTypeAndAccept = useCallback(async (redactionId, newType) => {
        await handleChangeTypeAndAccept(redactionId, newType);
        if (newType === 'DS_INFO') propagation.requestPropagationPreview(redactionId);
    }, [handleChangeTypeAndAccept, propagation]);

    const bulkChangeTypeAndAccept = useCallback(async (ids, newType) => {
        await handleBulkChangeTypeAndAccept(ids, newType);
        if (newType === 'DS_INFO') propagation.requestPropagationPreview(ids?.[0]);
    }, [handleBulkChangeTypeAndAccept, propagation]);

    const handleCloseRejectionDialog = useCallback(() => {
        setRejectionDialogOpen(false);
        setRejectionTarget(null);
        setBulkRejectIds([]);
        setMarkAllInCaseTarget(null);
    }, [setMarkAllInCaseTarget]);

    // Routes to the correct handler based on what triggered the rejection dialog.
    const handleRejectDialogSubmit = useCallback((id, reason) => {
        if (markAllInCaseTarget?.action === 'reject') {
            return handleMarkAllInCaseRejectConfirm(id, reason);
        }
        return handleRejectConfirm(id, reason);
    }, [markAllInCaseTarget, handleMarkAllInCaseRejectConfirm, handleRejectConfirm]);

    return {
        redactions,
        displaySections,
        pendingCount: displaySections.pending.total,

        display: {
            hoveredSuggestionId,
            scrollToId,
            onSuggestionMouseEnter: handleSuggestionMouseEnter,
            onSuggestionMouseLeave: handleSuggestionMouseLeave,
            onHighlightClick: handleHighlightClick,
            onRemoveScrollId: handleRemoveScrollId,
            onCardClick: handleCardClick,
        },

        manual: {
            anchor: manualRedactionAnchor,
            pending: pendingRedaction,
            onTextSelect: handleTextSelect,
            onCreate: handleCreateManualRedaction,
            onClose: handleCloseManualRedactionPopover,
            onContextSave: handleOnContextSave,
            onRemoveSelect: handleRemoveSelect,
            onUnhighlightClick: handleUnhighlightClick,
        },

        commands: {
            accept: handleAcceptSuggestion,
            bulkAccept: handleBulkAccept,
            rejectAsDisclosable: handleRejectAsDisclosable,
            changeTypeAndAccept,
            bulkChangeTypeAndAccept,
            openRejectDialog: handleOpenRejectDialog,
            openBulkRejectDialog: handleOpenBulkRejectDialog,
            splitMerge: handleSplitMerge,
            removeFromMerge: handleRemoveFromMerge,
            remove: handleRemoveRedaction,
        },

        markAllInCase: {
            target: markAllInCaseTarget,
            setTarget: setMarkAllInCaseTarget,
            onMarkAll: handleMarkAllInCase,
            onAcceptConfirm: handleMarkAllInCaseAcceptConfirm,
        },

        layout: {
            baseFontSize,
            canIncreaseFont,
            canDecreaseFont,
            sidebarWidth,
            onFontDecrease: handleFontDecrease,
            onFontIncrease: handleFontIncrease,
            onResizeStart: handleResizeStart,
        },

        tool: {
            activeType: activeHighlightType,
            onToggle: handleToggleHighlightTool,
        },

        history: {
            canUndo,
            canRedo,
            onUndo: undo,
            onRedo: redo,
        },

        document: {
            isLoading,
            isResubmitting,
            resubmitDialogOpen,
            setResubmitDialogOpen,
            onMarkAsComplete: handleMarkAsComplete,
            onResubmit: handleResubmit,
        },

        rejectionDialog: {
            open: rejectionDialogOpen,
            target: rejectionTarget,
            onClose: handleCloseRejectionDialog,
            onSubmit: handleRejectDialogSubmit,
        },

        propagation: {
            open: propagation.propagationDialogOpen,
            preview: propagation.propagationPreview,
            applying: propagation.propagationApplying,
            onConfirm: propagation.confirmPropagation,
            onCancel: propagation.cancelPropagation,
        },
    };
}

export function getDocumentViewerProps(store, document) {
    return {
        text: document?.extracted_text,
        tables: document?.extracted_tables,
        structure: document?.extracted_structure,
        redactions: store.redactions,
        pendingRedaction: store.manual.pending,
        hoveredSuggestionId: store.display.hoveredSuggestionId,
        onTextSelect: store.manual.onTextSelect,
        onRemoveSelect: store.manual.onRemoveSelect,
        onHighlightClick: store.display.onHighlightClick,
        onUnhighlightClick: store.manual.onUnhighlightClick,
        reviewComplete: store.pendingCount === 0,
        baseFontSize: store.layout.baseFontSize,
        activeHighlightType: store.tool.activeType,
    };
}

export function getRedactionSidebarProps(store, { exemptionTemplates, documentCompleted }) {
    return {
        redactions: store.displaySections,
        exemptionTemplates,
        onAccept: store.commands.accept,
        onReject: store.commands.openRejectDialog,
        onRemove: store.commands.remove,
        onChangeTypeAndAccept: store.commands.changeTypeAndAccept,
        onBulkChangeTypeAndAccept: store.commands.bulkChangeTypeAndAccept,
        onBulkAccept: store.commands.bulkAccept,
        onBulkReject: store.commands.openBulkRejectDialog,
        onRejectAsDisclosable: store.commands.rejectAsDisclosable,
        onMarkAllInCase: store.markAllInCase.onMarkAll,
        onSplitMerge: store.commands.splitMerge,
        onRemoveFromMerge: store.commands.removeFromMerge,
        onSuggestionMouseEnter: store.display.onSuggestionMouseEnter,
        onSuggestionMouseLeave: store.display.onSuggestionMouseLeave,
        scrollToId: store.display.scrollToId,
        removeScrollId: store.display.onRemoveScrollId,
        onContextSave: store.manual.onContextSave,
        onCardClick: store.display.onCardClick,
        activeHighlightType: store.tool.activeType,
        onToggleHighlightTool: store.tool.onToggle,
        documentCompleted,
        onUndo: store.history.onUndo,
        onRedo: store.history.onRedo,
        canUndo: store.history.canUndo,
        canRedo: store.history.canRedo,
    };
}
