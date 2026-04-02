import { useState, useCallback, useRef, useEffect } from 'react';
import { markAsComplete, resubmitDocument } from '@/services/documentService';
import toast from 'react-hot-toast';

const FONT_SIZE_STEPS = [0.75, 0.85, 1, 1.15, 1.3, 1.5];

export function useDocumentControls({ accessToken, undo, redo, clearHistory, currentDocument, router }) {
    const [isLoading, setIsLoading] = useState(false);
    const [isResubmitting, setIsResubmitting] = useState(false);
    const [resubmitDialogOpen, setResubmitDialogOpen] = useState(false);
    const [fontSizeIndex, setFontSizeIndex] = useState(2);
    const [activeHighlightType, setActiveHighlightType] = useState(null);

    const [sidebarWidth, setSidebarWidth] = useState(() => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('sidebarWidth');
            return saved ? parseInt(saved, 10) : 450;
        }
        return 450;
    });
    const isResizing = useRef(false);

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

    useEffect(() => {
        return () => {
            isResizing.current = false;
        };
    }, []);

    const handleToggleHighlightTool = useCallback((type) => {
        setActiveHighlightType(prev => prev === type ? null : type);
    }, []);

    const handleFontDecrease = useCallback(() => setFontSizeIndex(prev => Math.max(0, prev - 1)), []);
    const handleFontIncrease = useCallback(() => setFontSizeIndex(prev => Math.min(FONT_SIZE_STEPS.length - 1, prev + 1)), []);

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

    const handleMarkAsComplete = useCallback(async () => {
        setIsLoading(true);
        try {
            const updatedDocument = await markAsComplete(currentDocument.id, accessToken);
            console.log(updatedDocument);
            clearHistory();
            toast.success("Document is ready for disclosure.");
            router.push(`/cases/${currentDocument.case}`);
        } catch (error) {
            toast.error("Failed to mark document as complete. Please try again.");
        } finally {
            setIsLoading(false);
        }
    }, [currentDocument.id, currentDocument.case, accessToken, router, clearHistory]);

    const handleResubmit = useCallback(async () => {
        setIsResubmitting(true);
        try {
            await resubmitDocument(currentDocument.id, accessToken);
            clearHistory();
            toast.success("Document resubmitted for processing.");
            router.push(`/cases/${currentDocument.case}`);
        } catch (error) {
            toast.error("Failed to resubmit document. Please try again.");
        } finally {
            setIsResubmitting(false);
            setResubmitDialogOpen(false);
        }
    }, [currentDocument.id, currentDocument.case, accessToken, router, clearHistory]);

    return {
        isLoading,
        isResubmitting,
        resubmitDialogOpen,
        setResubmitDialogOpen,
        baseFontSize: FONT_SIZE_STEPS[fontSizeIndex],
        canIncreaseFont: fontSizeIndex < FONT_SIZE_STEPS.length - 1,
        canDecreaseFont: fontSizeIndex > 0,
        sidebarWidth,
        activeHighlightType,
        handleToggleHighlightTool,
        handleFontDecrease,
        handleFontIncrease,
        handleResizeStart,
        handleMarkAsComplete,
        handleResubmit,
    };
}
