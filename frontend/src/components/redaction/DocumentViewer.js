import React, { useRef } from 'react';
import { Paper, Box } from '@mui/material';

const HIGHLIGHT_COLORS = {
    PII: {
        suggestion: 'rgba(255, 214, 10, 0.4)',
        accepted: 'rgba(255, 214, 10, 0.7)',
        border: 'rgb(255, 165, 0)',
    },
    OP_DATA: {
        suggestion: 'rgba(0, 221, 255, 0.4)',
        accepted: 'rgba(0, 221, 255, 0.7)',
        border: 'rgb(0, 191, 255)',
    },
    DS_INFO: {
        suggestion: 'rgba(177, 156, 217, 0.5)',
        accepted: 'rgba(177, 156, 217, 0.8)',
        border: 'rgb(128, 0, 128)',
    },
    DEFAULT: {
        suggestion: 'rgba(200, 200, 200, 0.5)',
        accepted: 'rgba(200, 200, 200, 0.7)',
        border: 'grey',
    }
};

const getHighlightStyle = (mark, isHovered) => {
    const colors = HIGHLIGHT_COLORS[mark.redaction_type] || HIGHLIGHT_COLORS.DEFAULT;

    const baseBackgroundColor = mark.mark_type === 'accepted' ? colors.accepted : colors.suggestion;

    const style = {
        backgroundColor: isHovered ? colors.accepted : baseBackgroundColor,
        borderRadius: '3px',
        transition: 'all 0.2s ease-in-out',
        padding: '1px 2px',
        margin: '-1px -2px',
        border: '1px solid transparent',
    };

    if (isHovered) {
        style.border = `1px solid ${colors.border}`;
    }

    return style;
};

const DocumentViewer = ({ text, redactions, pendingRedaction, hoveredSuggestionId, onTextSelect }) => {
    const viewerRef = useRef(null);

    const handleMouseUp = () => {
        const selection = window.getSelection();
        if (!selection.isCollapsed && viewerRef.current && viewerRef.current.contains(selection.anchorNode)) {
            const selectedText = selection.toString();
            if (selectedText.trim() === '') return;

            const range = selection.getRangeAt(0);
            const preSelectionRange = document.createRange();
            preSelectionRange.selectNodeContents(viewerRef.current);
            preSelectionRange.setEnd(range.startContainer, range.startOffset);
            const start = preSelectionRange.toString().length;
            const end = start + selectedText.length;

            onTextSelect({ text: selectedText, start_char: start, end_char: end }, range);
            selection.removeAllRanges();
        }
    };

    const renderDocument = () => {
        if (!text) return null;

        const marksToRender = [];

        // Process all redactions to determine how they should be marked
        redactions.forEach(r => {
            if (r.is_accepted) {
                marksToRender.push({ ...r, mark_type: 'accepted' });
            } else if (r.is_suggestion) {
                marksToRender.push({ ...r, mark_type: 'suggestion' });
            }
        });

        // Add pending redaction for manual selection
        if (pendingRedaction) {
            marksToRender.push({
                ...pendingRedaction,
                id: 'pending-redaction',
                mark_type: 'pending',
            });
        }

        const sortedMarks = marksToRender.sort((a, b) => a.start_char - b.start_char);
        let lastIndex = 0;
        const parts = [];

        sortedMarks.forEach((mark) => {
            if (mark.start_char > lastIndex) {
                parts.push(text.substring(lastIndex, mark.start_char));
            }

            let style = {};
            const isHovered = mark.id === hoveredSuggestionId;

            if (mark.mark_type === 'accepted' || mark.mark_type === 'suggestion') {
                style = getHighlightStyle(mark, isHovered);
            } else if (mark.mark_type === 'pending') {
                style = { backgroundColor: 'rgba(255, 214, 10, 0.6)', borderRadius: '3px' };
            }

            parts.push(<Box component="span" sx={style} key={mark.id}>{mark.text}</Box>);
            lastIndex = Math.max(lastIndex, mark.end_char);
        });

        if (lastIndex < text.length) {
            parts.push(text.substring(lastIndex));
        }
        return parts.map((part, index) => <React.Fragment key={index}>{part}</React.Fragment>);
    };

    return (
        <Paper elevation={0} sx={{ p: 4, lineHeight: 2, fontSize: '1.1rem', whiteSpace: 'pre-wrap', flexGrow: 1, overflowY: 'auto', height: '100%' }} ref={viewerRef} onMouseUp={handleMouseUp}>
            {renderDocument()}
        </Paper>
    );
};

export default DocumentViewer;