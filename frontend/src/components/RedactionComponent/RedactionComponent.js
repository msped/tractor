"use client"

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Box, Typography, Button, Container, Tooltip, CircularProgress, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, IconButton } from '@mui/material';
import TextDecreaseIcon from '@mui/icons-material/TextDecrease';
import TextIncreaseIcon from '@mui/icons-material/TextIncrease';
import RefreshIcon from '@mui/icons-material/Refresh';
import UndoIcon from '@mui/icons-material/Undo';
import RedoIcon from '@mui/icons-material/Redo';
import NextLink from 'next/link';
import { RedactionSidebar } from '@/components/RedactionSidebar';
import { ManualRedactionPopover } from '@/components/ManualRedactionPopover';
import { RejectReasonDialog } from '@/components/RejectReasonDialog';
import { DocumentViewer } from '@/components/DocumentViewer';
import { markAsComplete, resubmitDocument } from '@/services/documentService'
import { createRedaction, updateRedaction, deleteRedaction, bulkUpdateRedactions, getExemptionTemplates } from '@/services/redactionService';
import { mergeAdjacentSpans, groupByTextAndType } from '@/utils/mergeRedactionSpans';
import { useUndoHistory } from '@/hooks/useUndoHistory';
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

    // State for active highlight tool (null | 'PII' | 'OP_DATA' | 'DS_INFO' | 'REMOVE')
    const [activeHighlightType, setActiveHighlightType] = useState(null);

    const handleToggleHighlightTool = useCallback((type) => {
        setActiveHighlightType(prev => prev === type ? null : type);
    }, []);

    // Undo/redo history
    const { push: pushHistory, undo, redo, clear: clearHistory, canUndo, canRedo } = useUndoHistory({ maxSize: 25 });

    // Keyboard shortcuts: Escape clears active tool; Ctrl+Z undoes; Ctrl+Y redoes
    useEffect(() => {
        const handler = (e) => {
            if (e.key === 'Escape') {
                setActiveHighlightType(null);
                return;
            }
            const inInput = ['INPUT', 'TEXTAREA'].includes(e.target.tagName) || e.target.isContentEditable;
            if (inInput) return;
            if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                undo();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
                e.preventDefault();
                redo();
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [undo, redo]);

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
        const prev = redactions.find(r => r.id === redactionId);
        if (!prev) return;
        try {
            const updatedRedaction = await updateRedaction(
                redactionId, { is_accepted: true },
                session?.access_token
            );
            setRedactions(prev => prev.map(r =>
                r.id === redactionId ? updatedRedaction : r
            ));
            pushHistory(
                async () => {
                    const reverted = await updateRedaction(redactionId, { is_accepted: false, justification: null }, session?.access_token);
                    setRedactions(s => s.map(r => r.id === redactionId ? reverted : r));
                },
                async () => {
                    const reapplied = await updateRedaction(redactionId, { is_accepted: true }, session?.access_token);
                    setRedactions(s => s.map(r => r.id === redactionId ? reapplied : r));
                }
            );
        } catch (error) {
            toast.error("Failed to accept suggestion. Please try again.");
        }
    }, [redactions, session?.access_token, pushHistory]);

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
            pushHistory(
                async () => {
                    const reverted = await bulkUpdateRedactions(document.id, ids, false, null, session?.access_token);
                    setRedactions(s => {
                        const m = new Map(reverted.map(r => [r.id, r]));
                        return s.map(r => m.has(r.id) ? m.get(r.id) : r);
                    });
                },
                async () => {
                    const reapplied = await bulkUpdateRedactions(document.id, ids, true, null, session?.access_token);
                    setRedactions(s => {
                        const m = new Map(reapplied.map(r => [r.id, r]));
                        return s.map(r => m.has(r.id) ? m.get(r.id) : r);
                    });
                }
            );
        } catch (error) {
            toast.error("Failed to accept suggestions. Please try again.");
        }
    }, [document.id, session?.access_token, pushHistory]);

    const handleRejectAsDisclosable = useCallback(async (ids, justification) => {
        setScrollToId(null);
        try {
            if (ids.length === 1) {
                const updated = await updateRedaction(
                    ids[0], { is_accepted: false, justification }, session?.access_token
                );
                setRedactions(prev => prev.map(r => r.id === ids[0] ? updated : r));
                pushHistory(
                    async () => {
                        const reverted = await updateRedaction(ids[0], { is_accepted: false, justification: null }, session?.access_token);
                        setRedactions(s => s.map(r => r.id === ids[0] ? reverted : r));
                    },
                    async () => {
                        const reapplied = await updateRedaction(ids[0], { is_accepted: false, justification }, session?.access_token);
                        setRedactions(s => s.map(r => r.id === ids[0] ? reapplied : r));
                    }
                );
            } else {
                const updatedList = await bulkUpdateRedactions(
                    document.id, ids, false, justification, session?.access_token
                );
                setRedactions(prev => {
                    const updatedMap = new Map(updatedList.map(r => [r.id, r]));
                    return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
                });
                pushHistory(
                    async () => {
                        const reverted = await bulkUpdateRedactions(document.id, ids, false, null, session?.access_token);
                        setRedactions(s => {
                            const m = new Map(reverted.map(r => [r.id, r]));
                            return s.map(r => m.has(r.id) ? m.get(r.id) : r);
                        });
                    },
                    async () => {
                        const reapplied = await bulkUpdateRedactions(document.id, ids, false, justification, session?.access_token);
                        setRedactions(s => {
                            const m = new Map(reapplied.map(r => [r.id, r]));
                            return s.map(r => m.has(r.id) ? m.get(r.id) : r);
                        });
                    }
                );
            }
        } catch (error) {
            toast.error("Failed to reject suggestion. Please try again.");
        }
    }, [document.id, session?.access_token, pushHistory]);

    const handleChangeTypeAndAccept = useCallback(async (redactionId, newType) => {
        setScrollToId(null);
        const prev = redactions.find(r => r.id === redactionId);
        if (!prev) return;
        const originalType = prev.redaction_type;
        const originalIsAccepted = prev.is_accepted;
        const originalIsSuggestion = prev.is_suggestion;
        try {
            const updatedRedaction = await updateRedaction(
                redactionId,
                { redaction_type: newType, is_accepted: true, is_suggestion: false },
                session?.access_token
            );
            setRedactions(prev => prev.map(r =>
                r.id === redactionId ? updatedRedaction : r
            ));
            toast.success("Suggestion type changed and accepted.");
            pushHistory(
                async () => {
                    const reverted = await updateRedaction(redactionId, { redaction_type: originalType, is_accepted: originalIsAccepted, is_suggestion: originalIsSuggestion }, session?.access_token);
                    setRedactions(s => s.map(r => r.id === redactionId ? reverted : r));
                },
                async () => {
                    const reapplied = await updateRedaction(redactionId, { redaction_type: newType, is_accepted: true, is_suggestion: false }, session?.access_token);
                    setRedactions(s => s.map(r => r.id === redactionId ? reapplied : r));
                }
            );
        } catch (error) {
            toast.error("Failed to change suggestion type. Please try again.");
        }
    }, [redactions, session?.access_token, pushHistory]);

    const handleBulkChangeTypeAndAccept = useCallback(async (ids, newType) => {
        setScrollToId(null);
        const originals = ids.map(id => redactions.find(r => r.id === id)).filter(Boolean);
        try {
            const updates = await Promise.all(
                ids.map(id => updateRedaction(id, { redaction_type: newType, is_accepted: true, is_suggestion: false }, session?.access_token))
            );
            setRedactions(prev => {
                const updatedMap = new Map(updates.map(r => [r.id, r]));
                return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
            });
            toast.success("Suggestions type changed and accepted.");
            pushHistory(
                async () => {
                    const reverted = await Promise.all(
                        originals.map(o => updateRedaction(o.id, { redaction_type: o.redaction_type, is_accepted: o.is_accepted, is_suggestion: o.is_suggestion }, session?.access_token))
                    );
                    setRedactions(s => {
                        const m = new Map(reverted.map(r => [r.id, r]));
                        return s.map(r => m.has(r.id) ? m.get(r.id) : r);
                    });
                },
                async () => {
                    const reapplied = await Promise.all(
                        ids.map(id => updateRedaction(id, { redaction_type: newType, is_accepted: true, is_suggestion: false }, session?.access_token))
                    );
                    setRedactions(s => {
                        const m = new Map(reapplied.map(r => [r.id, r]));
                        return s.map(r => m.has(r.id) ? m.get(r.id) : r);
                    });
                }
            );
        } catch (error) {
            toast.error("Failed to change suggestion types. Please try again.");
        }
    }, [redactions, session?.access_token, pushHistory]);

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
            const capturedIds = [...bulkRejectIds];
            try {
                const updatedRedactions = await bulkUpdateRedactions(
                    document.id, capturedIds, false, reason, session?.access_token
                );
                setRedactions(prev => {
                    const updatedMap = new Map(updatedRedactions.map(r => [r.id, r]));
                    return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
                });
                pushHistory(
                    async () => {
                        const reverted = await bulkUpdateRedactions(document.id, capturedIds, false, null, session?.access_token);
                        setRedactions(s => {
                            const m = new Map(reverted.map(r => [r.id, r]));
                            return s.map(r => m.has(r.id) ? m.get(r.id) : r);
                        });
                    },
                    async () => {
                        const reapplied = await bulkUpdateRedactions(document.id, capturedIds, false, reason, session?.access_token);
                        setRedactions(s => {
                            const m = new Map(reapplied.map(r => [r.id, r]));
                            return s.map(r => m.has(r.id) ? m.get(r.id) : r);
                        });
                    }
                );
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
                pushHistory(
                    async () => {
                        const reverted = await updateRedaction(redactionId, { is_accepted: false, justification: null }, session?.access_token);
                        setRedactions(s => s.map(r => r.id === redactionId ? reverted : r));
                    },
                    async () => {
                        const reapplied = await updateRedaction(redactionId, { is_accepted: false, justification: reason }, session?.access_token);
                        setRedactions(s => s.map(r => r.id === redactionId ? reapplied : r));
                    }
                );
            } catch (error) {
                toast.error("Failed to reject suggestion. Please try again.");
            } finally {
                setRejectionDialogOpen(false);
                setRejectionTarget(null);
            }
        }
    }, [bulkRejectIds, document.id, session?.access_token, pushHistory]);

    const handleSplitMerge = useCallback((mergeKey) => {
        setSplitMerges(prev => new Set(prev).add(mergeKey));
        pushHistory(
            async () => setSplitMerges(prev => { const n = new Set(prev); n.delete(mergeKey); return n; }),
            async () => setSplitMerges(prev => new Set(prev).add(mergeKey))
        );
    }, [pushHistory]);

    // Internal helper: perform the remove API call + state update without pushing history.
    // Returns the snapshot of the redaction before removal, or null on failure.
    const _removeRedactionById = useCallback(async (redactionToRemove) => {
        if (!redactionToRemove.is_suggestion) {
            await deleteRedaction(redactionToRemove.id, session?.access_token);
            setRedactions(prev => prev.filter(r => r.id !== redactionToRemove.id));
            toast.success("Redaction deleted.");
        } else {
            const updated = await updateRedaction(
                redactionToRemove.id,
                { is_accepted: false, justification: null },
                session?.access_token
            );
            setRedactions(prev => prev.map(r => r.id === redactionToRemove.id ? updated : r));
            toast.success("Suggestion reverted to pending.");
        }
    }, [session?.access_token]);

    const handleRemoveRedaction = useCallback(async (redactionId) => {
        const snap = redactions.find(r => r.id === redactionId);
        if (!snap) return;
        try {
            await _removeRedactionById(snap);
            if (!snap.is_suggestion) {
                // Manual redaction deleted — undo recreates it
                let currentId = snap.id;
                pushHistory(
                    async () => {
                        const created = await createRedaction(document.id, {
                            text: snap.text,
                            start_char: snap.start_char,
                            end_char: snap.end_char,
                            document: document.id,
                            redaction_type: snap.redaction_type,
                            is_suggestion: false,
                            is_accepted: true,
                        }, session?.access_token);
                        currentId = created.id;
                        setRedactions(prev => [...prev, created]);
                    },
                    async () => {
                        await deleteRedaction(currentId, session?.access_token);
                        setRedactions(prev => prev.filter(r => r.id !== currentId));
                    }
                );
            } else {
                // AI suggestion reverted to pending — undo restores prior state
                pushHistory(
                    async () => {
                        const restored = await updateRedaction(snap.id, { is_accepted: snap.is_accepted, justification: snap.justification }, session?.access_token);
                        setRedactions(prev => prev.map(r => r.id === snap.id ? restored : r));
                    },
                    async () => {
                        const reverted = await updateRedaction(snap.id, { is_accepted: false, justification: null }, session?.access_token);
                        setRedactions(prev => prev.map(r => r.id === snap.id ? reverted : r));
                    }
                );
            }
        } catch (error) {
            toast.error("Failed to remove redaction. Please try again.");
        }
    }, [redactions, session?.access_token, pushHistory, _removeRedactionById, document.id]);

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

    const handleCreateManualRedaction = useCallback(async (redactionType, selectionOverride = null) => {
        if (redactionType === 'REMOVE') return;
        const sel = selectionOverride ?? newSelection;
        const isToolMode = selectionOverride !== null;
        if (!sel) return;

        // Find any existing redactions that overlap with the selection
        const overlapping = redactions.filter(r =>
            r.start_char < sel.end_char && r.end_char > sel.start_char
        );

        if (overlapping.length > 0) {
            if (isToolMode) {
                // Tool mode: accept/update every overlapping redaction, preserving is_suggestion,
                // then create new user redactions for any uncovered gaps within the selection.
                const originalOverlapping = overlapping.map(r => ({ id: r.id, redaction_type: r.redaction_type, is_accepted: r.is_accepted, is_suggestion: r.is_suggestion }));
                let currentCreatedIds = [];
                try {
                    const updates = await Promise.all(
                        overlapping.map(r => updateRedaction(r.id, { redaction_type: redactionType, is_accepted: true }, session?.access_token))
                    );
                    setRedactions(prev => {
                        const updatedMap = new Map(updates.map(r => [r.id, r]));
                        return prev.map(r => updatedMap.has(r.id) ? updatedMap.get(r.id) : r);
                    });
                } catch (error) {
                    handleCloseManualRedactionPopover();
                    toast.error("Failed to update redactions. Please try again.");
                    return;
                }

                // Find gaps within the selection not covered by any overlapping redaction
                const sorted = [...overlapping].sort((a, b) => a.start_char - b.start_char);
                const gaps = [];
                let cursor = sel.start_char;
                for (const r of sorted) {
                    const rStart = Math.max(r.start_char, sel.start_char);
                    if (rStart > cursor) gaps.push({ start_char: cursor, end_char: rStart });
                    cursor = Math.max(cursor, Math.min(r.end_char, sel.end_char));
                }
                if (cursor < sel.end_char) gaps.push({ start_char: cursor, end_char: sel.end_char });

                if (gaps.length > 0) {
                    const docText = document.extracted_text || '';
                    const substantiveGaps = gaps.filter(gap =>
                        docText.substring(gap.start_char, gap.end_char).trim().length > 0
                    );
                    if (substantiveGaps.length > 0) {
                        try {
                            const created = await Promise.all(
                                substantiveGaps.map(gap => createRedaction(document.id, {
                                    text: docText.substring(gap.start_char, gap.end_char),
                                    start_char: gap.start_char,
                                    end_char: gap.end_char,
                                    document: document.id,
                                    redaction_type: redactionType,
                                    is_suggestion: false,
                                    is_accepted: true,
                                }, session?.access_token))
                            );
                            currentCreatedIds = created.map(r => r.id);
                            setRedactions(prev => [...prev, ...created]);
                        } catch (error) {
                            toast.error("Failed to redact uncovered areas. Please try again.");
                        }
                    }
                }

                pushHistory(
                    async () => {
                        // Delete gap-filled redactions
                        await Promise.all(currentCreatedIds.map(id => deleteRedaction(id, session?.access_token)));
                        setRedactions(prev => prev.filter(r => !currentCreatedIds.includes(r.id)));
                        // Revert updated overlapping redactions
                        const reverted = await Promise.all(
                            originalOverlapping.map(o => updateRedaction(o.id, { redaction_type: o.redaction_type, is_accepted: o.is_accepted }, session?.access_token))
                        );
                        setRedactions(prev => {
                            const m = new Map(reverted.map(r => [r.id, r]));
                            return prev.map(r => m.has(r.id) ? m.get(r.id) : r);
                        });
                    },
                    async () => {
                        const reUpdated = await Promise.all(
                            originalOverlapping.map(o => updateRedaction(o.id, { redaction_type: redactionType, is_accepted: true }, session?.access_token))
                        );
                        setRedactions(prev => {
                            const m = new Map(reUpdated.map(r => [r.id, r]));
                            return prev.map(r => m.has(r.id) ? m.get(r.id) : r);
                        });
                        if (gaps.length > 0) {
                            const docText = document.extracted_text || '';
                            const substantiveGaps = gaps.filter(gap =>
                                docText.substring(gap.start_char, gap.end_char).trim().length > 0
                            );
                            if (substantiveGaps.length > 0) {
                                const reCreated = await Promise.all(
                                    substantiveGaps.map(gap => createRedaction(document.id, {
                                        text: docText.substring(gap.start_char, gap.end_char),
                                        start_char: gap.start_char,
                                        end_char: gap.end_char,
                                        document: document.id,
                                        redaction_type: redactionType,
                                        is_suggestion: false,
                                        is_accepted: true,
                                    }, session?.access_token))
                                );
                                currentCreatedIds = reCreated.map(r => r.id);
                                setRedactions(prev => [...prev, ...reCreated]);
                            }
                        }
                    }
                );

                handleCloseManualRedactionPopover();
                return;
            }

            // Popover mode
            const sameType = overlapping.every(r => r.redaction_type === redactionType);
            if (sameType) {
                handleCloseManualRedactionPopover();
                toast("This text is already redacted with this classification.");
                return;
            }
            // Different classification — overwrite the existing redaction(s)
            const originalOverlapping = overlapping.map(r => ({ id: r.id, redaction_type: r.redaction_type, is_accepted: r.is_accepted, is_suggestion: r.is_suggestion }));
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
                pushHistory(
                    async () => {
                        const reverted = await Promise.all(
                            originalOverlapping.map(o => updateRedaction(o.id, { redaction_type: o.redaction_type, is_accepted: o.is_accepted, is_suggestion: o.is_suggestion }, session?.access_token))
                        );
                        setRedactions(prev => {
                            const m = new Map(reverted.map(r => [r.id, r]));
                            return prev.map(r => m.has(r.id) ? m.get(r.id) : r);
                        });
                    },
                    async () => {
                        const reapplied = await Promise.all(
                            originalOverlapping.map(o => updateRedaction(o.id, { redaction_type: redactionType, is_accepted: true, is_suggestion: false }, session?.access_token))
                        );
                        setRedactions(prev => {
                            const m = new Map(reapplied.map(r => [r.id, r]));
                            return prev.map(r => m.has(r.id) ? m.get(r.id) : r);
                        });
                    }
                );
            } catch (error) {
                handleCloseManualRedactionPopover();
                toast.error("Failed to update redaction. Please try again.");
            }
            return;
        }

        const newRedaction = {
            ...sel,
            document: document.id,
            redaction_type: redactionType,
            is_suggestion: false,
            is_accepted: true,
        };
        let currentCreatedId = null;
        try {
            const createdRedaction = await createRedaction(document.id, newRedaction, session?.access_token);
            currentCreatedId = createdRedaction.id;
            setRedactions(prev => [...prev, createdRedaction]);
            handleCloseManualRedactionPopover();
            toast.success("Redaction created successfully.");
            pushHistory(
                async () => {
                    await deleteRedaction(currentCreatedId, session?.access_token);
                    setRedactions(prev => prev.filter(r => r.id !== currentCreatedId));
                },
                async () => {
                    const reCreated = await createRedaction(document.id, newRedaction, session?.access_token);
                    currentCreatedId = reCreated.id;
                    setRedactions(prev => [...prev, reCreated]);
                }
            );
        } catch (error) {
            handleCloseManualRedactionPopover();
            toast.error("Failed to create redaction. Please try again.");
        }

    }, [newSelection, document.id, document.extracted_text, handleCloseManualRedactionPopover, session?.access_token, redactions, pushHistory]);

    const handleTextSelect = useCallback((selection, rect) => {
        if (activeHighlightType === 'REMOVE') return;
        if (activeHighlightType) {
            setNewSelection(selection);
            setPendingRedaction(selection);
            handleCreateManualRedaction(activeHighlightType, selection);
            return;
        }
        setNewSelection(selection);
        setPendingRedaction(selection);
        const virtualEl = { getBoundingClientRect: () => rect, nodeType: 1 };
        setManualRedactionAnchor(virtualEl);
    }, [activeHighlightType, handleCreateManualRedaction]);

    // When Remove tool is active and text is selected, trim/remove the overlapping accepted redaction(s).
    const handleRemoveSelect = useCallback(async (selection) => {
        const selStart = selection.start_char;
        const selEnd = selection.end_char;
        const extractedText = document.extracted_text;

        const overlapping = redactions.filter(r =>
            (r.is_accepted || !r.is_suggestion) &&
            r.start_char < selEnd && r.end_char > selStart
        );

        if (overlapping.length === 0) return;

        const snapshots = overlapping.map(r => ({ ...r }));

        // For split operations a new record is created; track its ID so undo can delete it.
        // Using a mutable ref-style variable so redo can keep it current after re-creation.
        let splitCreatedId = null;

        try {
            for (const r of overlapping) {
                const fullyContained = selStart <= r.start_char && selEnd >= r.end_char;
                const trimEnd = !fullyContained && selEnd >= r.end_char;
                const trimStart = !fullyContained && selStart <= r.start_char;
                const splitMiddle = !fullyContained && !trimEnd && !trimStart;

                if (fullyContained) {
                    if (!r.is_suggestion) {
                        await deleteRedaction(r.id, session?.access_token);
                        setRedactions(prev => prev.filter(x => x.id !== r.id));
                    } else {
                        const updated = await updateRedaction(r.id, { is_accepted: false, justification: null }, session?.access_token);
                        setRedactions(prev => prev.map(x => x.id === r.id ? updated : x));
                    }
                } else if (trimEnd) {
                    const updated = await updateRedaction(r.id, {
                        end_char: selStart,
                        text: extractedText.substring(r.start_char, selStart),
                    }, session?.access_token);
                    setRedactions(prev => prev.map(x => x.id === r.id ? updated : x));
                } else if (trimStart) {
                    const updated = await updateRedaction(r.id, {
                        start_char: selEnd,
                        text: extractedText.substring(selEnd, r.end_char),
                    }, session?.access_token);
                    setRedactions(prev => prev.map(x => x.id === r.id ? updated : x));
                } else if (splitMiddle) {
                    const updatedFirst = await updateRedaction(r.id, {
                        end_char: selStart,
                        text: extractedText.substring(r.start_char, selStart),
                    }, session?.access_token);
                    setRedactions(prev => prev.map(x => x.id === r.id ? updatedFirst : x));
                    const createdSecond = await createRedaction(document.id, {
                        text: extractedText.substring(selEnd, r.end_char),
                        start_char: selEnd,
                        end_char: r.end_char,
                        document: document.id,
                        redaction_type: r.redaction_type,
                        is_suggestion: r.is_suggestion,
                        is_accepted: r.is_accepted,
                        justification: r.justification,
                    }, session?.access_token);
                    setRedactions(prev => [...prev, createdSecond]);
                    splitCreatedId = createdSecond.id;
                }
            }
        } catch {
            toast.error("Failed to modify redaction. Please try again.");
            return;
        }

        pushHistory(
            async () => {
                // Undo: restore all original positions/state
                for (const snap of snapshots) {
                    const fullyContained = selStart <= snap.start_char && selEnd >= snap.end_char;
                    const splitMiddle = !fullyContained && selStart > snap.start_char && selEnd < snap.end_char;

                    if (fullyContained) {
                        if (!snap.is_suggestion) {
                            const created = await createRedaction(document.id, {
                                text: snap.text, start_char: snap.start_char, end_char: snap.end_char,
                                document: document.id, redaction_type: snap.redaction_type,
                                is_suggestion: false, is_accepted: true,
                            }, session?.access_token);
                            setRedactions(prev => [...prev, created]);
                        } else {
                            const restored = await updateRedaction(snap.id, { is_accepted: snap.is_accepted, justification: snap.justification }, session?.access_token);
                            setRedactions(prev => prev.map(r => r.id === snap.id ? restored : r));
                        }
                    } else {
                        const restored = await updateRedaction(snap.id, {
                            start_char: snap.start_char, end_char: snap.end_char, text: snap.text,
                        }, session?.access_token);
                        setRedactions(prev => prev.map(r => r.id === snap.id ? restored : r));
                        if (splitMiddle && splitCreatedId) {
                            await deleteRedaction(splitCreatedId, session?.access_token);
                            setRedactions(prev => prev.filter(r => r.id !== splitCreatedId));
                            splitCreatedId = null;
                        }
                    }
                }
            },
            async () => {
                // Redo: re-apply the trim/remove operations
                for (const snap of snapshots) {
                    const fullyContained = selStart <= snap.start_char && selEnd >= snap.end_char;
                    const trimEnd = !fullyContained && selEnd >= snap.end_char;
                    const trimStart = !fullyContained && selStart <= snap.start_char;
                    const splitMiddle = !fullyContained && !trimEnd && !trimStart;

                    if (fullyContained) {
                        if (!snap.is_suggestion) {
                            await deleteRedaction(snap.id, session?.access_token);
                            setRedactions(prev => prev.filter(r => r.id !== snap.id));
                        } else {
                            const updated = await updateRedaction(snap.id, { is_accepted: false, justification: null }, session?.access_token);
                            setRedactions(prev => prev.map(r => r.id === snap.id ? updated : r));
                        }
                    } else if (trimEnd) {
                        const updated = await updateRedaction(snap.id, {
                            end_char: selStart, text: extractedText.substring(snap.start_char, selStart),
                        }, session?.access_token);
                        setRedactions(prev => prev.map(r => r.id === snap.id ? updated : r));
                    } else if (trimStart) {
                        const updated = await updateRedaction(snap.id, {
                            start_char: selEnd, text: extractedText.substring(selEnd, snap.end_char),
                        }, session?.access_token);
                        setRedactions(prev => prev.map(r => r.id === snap.id ? updated : r));
                    } else if (splitMiddle) {
                        const updated = await updateRedaction(snap.id, {
                            end_char: selStart, text: extractedText.substring(snap.start_char, selStart),
                        }, session?.access_token);
                        setRedactions(prev => prev.map(r => r.id === snap.id ? updated : r));
                        const created = await createRedaction(document.id, {
                            text: extractedText.substring(selEnd, snap.end_char),
                            start_char: selEnd, end_char: snap.end_char,
                            document: document.id, redaction_type: snap.redaction_type,
                            is_suggestion: snap.is_suggestion, is_accepted: snap.is_accepted,
                            justification: snap.justification,
                        }, session?.access_token);
                        setRedactions(prev => [...prev, created]);
                        splitCreatedId = created.id;
                    }
                }
            }
        );
    }, [redactions, pushHistory, session?.access_token, document.id, document.extracted_text]);

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

    const [scrollToDocumentId, setScrollToDocumentId] = useState(null);

    const handleCardClick = useCallback((redactionId) => {
        setScrollToDocumentId(redactionId);
    }, []);

    useEffect(() => {
        if (!scrollToDocumentId) return;
        const el = window.document.querySelector(`[data-redaction-id="${scrollToDocumentId}"]`);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        setScrollToDocumentId(null);
    }, [scrollToDocumentId]);

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

    // When the REMOVE tool is active and a highlight is clicked in the document,
    // find all IDs in the same merge group and remove them as a single undo step.
    const handleUnhighlightClick = useCallback(async (clickedId) => {
        // Find all IDs in the same merge group
        let targetIds = [clickedId];
        outer: for (const section of Object.values(displaySections)) {
            for (const item of section.items) {
                const candidates = item.isGroup
                    ? item.items.flatMap(gi => gi.ids ?? [gi.id])
                    : (item.ids ?? [item.id]);
                if (candidates.includes(clickedId)) {
                    targetIds = candidates;
                    break outer;
                }
            }
        }

        const snapshots = targetIds.map(id => redactions.find(r => r.id === id)).filter(Boolean);
        if (snapshots.length === 0) return;

        try {
            await Promise.all(snapshots.map(snap => _removeRedactionById(snap)));
        } catch {
            toast.error("Failed to remove redaction. Please try again.");
            return;
        }

        pushHistory(
            async () => {
                for (const snap of snapshots) {
                    if (!snap.is_suggestion) {
                        const created = await createRedaction(document.id, {
                            text: snap.text,
                            start_char: snap.start_char,
                            end_char: snap.end_char,
                            document: document.id,
                            redaction_type: snap.redaction_type,
                            is_suggestion: false,
                            is_accepted: true,
                        }, session?.access_token);
                        setRedactions(prev => [...prev, created]);
                    } else {
                        const restored = await updateRedaction(snap.id, { is_accepted: snap.is_accepted, justification: snap.justification }, session?.access_token);
                        setRedactions(prev => prev.map(r => r.id === snap.id ? restored : r));
                    }
                }
            },
            async () => {
                await Promise.all(snapshots.map(snap => _removeRedactionById(snap)));
            }
        );
    }, [displaySections, redactions, pushHistory, _removeRedactionById, document.id, session?.access_token]);

    const handleMarkAsComplete = useCallback(async () => {
        setIsLoading(true);
        try {
            const updatedDocument = await markAsComplete(currentDocument.id, session?.access_token);
            console.log(updatedDocument);
            clearHistory();
            toast.success("Document is ready for disclosure.");
            router.push(`/cases/${currentDocument.case}`);
        } catch (error) {
            toast.error("Failed to mark document as complete. Please try again.");
        } finally {
            setIsLoading(false);
        }
    }, [currentDocument.id, currentDocument.case, session?.access_token, router, clearHistory]);

    const handleResubmit = useCallback(async () => {
        setIsResubmitting(true);
        try {
            await resubmitDocument(currentDocument.id, session?.access_token);
            clearHistory();
            toast.success("Document resubmitted for processing.");
            router.push(`/cases/${currentDocument.case}`);
        } catch (error) {
            toast.error("Failed to resubmit document. Please try again.");
        } finally {
            setIsResubmitting(false);
            setResubmitDialogOpen(false);
        }
    }, [currentDocument.id, currentDocument.case, session?.access_token, router, clearHistory]);

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
                        <Tooltip title="Undo (Ctrl+Z)">
                            <span>
                                <IconButton
                                    aria-label="Undo"
                                    onClick={undo}
                                    disabled={!canUndo}
                                    size="small"
                                >
                                    <UndoIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Redo (Ctrl+Y)">
                            <span>
                                <IconButton
                                    aria-label="Redo"
                                    onClick={redo}
                                    disabled={!canRedo}
                                    size="small"
                                >
                                    <RedoIcon />
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
                    exemptionTemplates={exemptionTemplates}
                    activeHighlightType={activeHighlightType}
                    onToggleHighlightTool={handleToggleHighlightTool}
                    documentCompleted={currentDocument.status === 'Completed'}
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
