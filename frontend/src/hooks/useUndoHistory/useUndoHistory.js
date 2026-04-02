import { useRef, useState, useCallback } from 'react';

export function useUndoHistory({ maxSize = 25 } = {}) {
    const undoStack = useRef([]);
    const redoStack = useRef([]);
    const [canUndo, setCanUndo] = useState(false);
    const [canRedo, setCanRedo] = useState(false);

    const syncBooleans = useCallback(() => {
        setCanUndo(undoStack.current.length > 0);
        setCanRedo(redoStack.current.length > 0);
    }, []);

    const push = useCallback((undoFn, redoFn) => {
        undoStack.current.push({ undo: undoFn, redo: redoFn });
        if (undoStack.current.length > maxSize) {
            undoStack.current.shift();
        }
        redoStack.current = [];
        syncBooleans();
    }, [maxSize, syncBooleans]);

    const undo = useCallback(async () => {
        if (undoStack.current.length === 0) return;
        const entry = undoStack.current.pop();
        await entry.undo();
        redoStack.current.push(entry);
        syncBooleans();
    }, [syncBooleans]);

    const redo = useCallback(async () => {
        if (redoStack.current.length === 0) return;
        const entry = redoStack.current.pop();
        await entry.redo();
        undoStack.current.push(entry);
        syncBooleans();
    }, [syncBooleans]);

    const clear = useCallback(() => {
        undoStack.current = [];
        redoStack.current = [];
        syncBooleans();
    }, [syncBooleans]);

    return { push, undo, redo, clear, canUndo, canRedo };
}
