import React, { useState } from 'react';
import { useUndoHistory } from './useUndoHistory';

// Thin harness component to exercise the hook
function Harness({ maxSize, onPushRef, onUndoRef, onRedoRef, onClearRef }) {
    const { push, undo, redo, clear, canUndo, canRedo } = useUndoHistory({ maxSize });
    const [log, setLog] = useState([]);

    // Expose hook methods via refs so tests can call them
    if (onPushRef) onPushRef.current = push;
    if (onUndoRef) onUndoRef.current = undo;
    if (onRedoRef) onRedoRef.current = redo;
    if (onClearRef) onClearRef.current = clear;

    return (
        <div>
            <div data-testid="can-undo">{canUndo ? 'true' : 'false'}</div>
            <div data-testid="can-redo">{canRedo ? 'true' : 'false'}</div>
            <div data-testid="log">{log.join(',')}</div>
            <button
                data-testid="push-btn"
                onClick={() => {
                    const entry = log.length;
                    push(
                        async () => setLog(prev => [...prev, `undo-${entry}`]),
                        async () => setLog(prev => [...prev, `redo-${entry}`]),
                    );
                    setLog(prev => [...prev, `push-${entry}`]);
                }}
            >
                Push
            </button>
            <button data-testid="undo-btn" onClick={undo}>Undo</button>
            <button data-testid="redo-btn" onClick={redo}>Redo</button>
            <button data-testid="clear-btn" onClick={clear}>Clear</button>
        </div>
    );
}

describe('useUndoHistory', () => {
    it('starts with canUndo=false and canRedo=false', () => {
        cy.mount(<Harness />);
        cy.get('[data-testid="can-undo"]').should('have.text', 'false');
        cy.get('[data-testid="can-redo"]').should('have.text', 'false');
    });

    it('canUndo becomes true after a push', () => {
        cy.mount(<Harness />);
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="can-undo"]').should('have.text', 'true');
        cy.get('[data-testid="can-redo"]').should('have.text', 'false');
    });

    it('undo executes the undo fn and moves entry to redo stack', () => {
        cy.mount(<Harness />);
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="undo-btn"]').click();
        cy.get('[data-testid="can-undo"]').should('have.text', 'false');
        cy.get('[data-testid="can-redo"]').should('have.text', 'true');
        cy.get('[data-testid="log"]').should('contain', 'undo-0');
    });

    it('redo executes the redo fn and moves entry back to undo stack', () => {
        cy.mount(<Harness />);
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="undo-btn"]').click();
        cy.get('[data-testid="redo-btn"]').click();
        cy.get('[data-testid="can-undo"]').should('have.text', 'true');
        cy.get('[data-testid="can-redo"]').should('have.text', 'false');
        cy.get('[data-testid="log"]').should('contain', 'redo-0');
    });

    it('pushing a new action after undo clears the redo stack', () => {
        cy.mount(<Harness />);
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="undo-btn"]').click();
        cy.get('[data-testid="can-redo"]').should('have.text', 'true');
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="can-redo"]').should('have.text', 'false');
    });

    it('undo and redo do nothing when their respective stacks are empty', () => {
        cy.mount(<Harness />);
        cy.get('[data-testid="undo-btn"]').click();
        cy.get('[data-testid="redo-btn"]').click();
        cy.get('[data-testid="log"]').should('have.text', '');
        cy.get('[data-testid="can-undo"]').should('have.text', 'false');
        cy.get('[data-testid="can-redo"]').should('have.text', 'false');
    });

    it('clear resets both stacks and booleans', () => {
        cy.mount(<Harness />);
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="can-undo"]').should('have.text', 'true');
        cy.get('[data-testid="clear-btn"]').click();
        cy.get('[data-testid="can-undo"]').should('have.text', 'false');
        cy.get('[data-testid="can-redo"]').should('have.text', 'false');
    });

    it('respects maxSize by dropping the oldest entry', () => {
        cy.mount(<Harness maxSize={3} />);
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="push-btn"]').click();
        cy.get('[data-testid="push-btn"]').click(); // 4th push — oldest (push-0) dropped
        // undo 3 times — should succeed
        cy.get('[data-testid="undo-btn"]').click();
        cy.get('[data-testid="undo-btn"]').click();
        cy.get('[data-testid="undo-btn"]').click();
        cy.get('[data-testid="can-undo"]').should('have.text', 'false');
        // stack had only 3 entries after the 4th push
        cy.get('[data-testid="log"]').should('contain', 'undo-3');
        cy.get('[data-testid="log"]').should('contain', 'undo-2');
        cy.get('[data-testid="log"]').should('contain', 'undo-1');
        cy.get('[data-testid="log"]').should('not.contain', 'undo-0');
    });

    it('executes undo and redo in LIFO order', () => {
        cy.mount(<Harness />);
        cy.get('[data-testid="push-btn"]').click(); // push-0
        cy.get('[data-testid="push-btn"]').click(); // push-1
        cy.get('[data-testid="undo-btn"]').click(); // undoes push-1
        cy.get('[data-testid="log"]').should('contain', 'undo-1');
        cy.get('[data-testid="undo-btn"]').click(); // undoes push-0
        cy.get('[data-testid="log"]').should('contain', 'undo-0');
    });
});
