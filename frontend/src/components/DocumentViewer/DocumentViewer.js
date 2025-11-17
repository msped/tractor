import React, { useRef } from 'react';
import { Paper, Box } from '@mui/material';

const HIGHLIGHT_COLORS = {
    // For pending suggestions, which are always yellow
    PENDING: {
        suggestion: 'rgba(255, 214, 10, 0.4)',
        accepted: 'rgba(255, 214, 10, 0.7)', // More opaque for hover
        border: 'rgb(255, 165, 0)',
    },
    // For accepted redactions, colored by type
    PII: { // Third-Party PII -> Green
        suggestion: 'rgba(46, 204, 113, 0.4)',
        accepted: 'rgba(46, 204, 113, 0.7)',
        border: 'rgb(39, 174, 96)',
    },
    OP_DATA: { // Operational Data -> Blue
        suggestion: 'rgba(0, 221, 255, 0.4)',
        accepted: 'rgba(0, 221, 255, 0.7)',
        border: 'rgb(0, 191, 255)',
    },
    DS_INFO: { // Data Subject Info -> Purple
        suggestion: 'rgba(177, 156, 217, 0.5)',
        accepted: 'rgba(177, 156, 217, 0.8)',
        border: 'rgb(128, 0, 128)',
    },
    REJECTED: { // For rejected suggestions
        suggestion: 'rgba(189, 195, 199, 0.5)', // A neutral grey
        accepted: 'rgba(127, 140, 141, 0.7)', // More opaque for hover
        border: 'rgb(149, 165, 166)',
    },
    DEFAULT: { // Fallback
        suggestion: 'rgba(200, 200, 200, 0.5)',
        accepted: 'rgba(200, 200, 200, 0.7)',
        border: 'grey',
    }
};

const getHighlightStyle = (mark, isHovered, viewMode) => {
    if (viewMode === 'final') {
        return {
            backgroundColor: 'black',
            color: 'black',
            borderRadius: '3px',
            padding: '1px 2px',
            margin: '-1px -2px',
            userSelect: 'none',
        };
    }

    if (viewMode === 'color-coded') {
        const colors = HIGHLIGHT_COLORS[mark.redaction_type] || HIGHLIGHT_COLORS.DEFAULT;
        return {
            backgroundColor: colors.accepted, // Use the more opaque color
            borderRadius: '3px',
            padding: '1px 2px',
            margin: '-1px -2px',
        };
    }

    let colors;

    if (mark.mark_type === 'suggestion') {
        // All pending suggestions are yellow, regardless of their type.
        colors = HIGHLIGHT_COLORS.PENDING;
    } else if (mark.mark_type === 'rejected') {
        colors = HIGHLIGHT_COLORS.REJECTED;
    } else { // 'accepted'
        // Accepted redactions are colored by their specific type.
        colors = HIGHLIGHT_COLORS[mark.redaction_type] || HIGHLIGHT_COLORS.DEFAULT;
    }

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

export const DocumentViewer = ({ text, redactions, pendingRedaction, hoveredSuggestionId, onTextSelect, onHighlightClick, reviewComplete, viewMode = 'review' }) => {
    const viewerRef = useRef(null);

    const handleMouseUp = () => {
        // onTextSelect is only passed in review mode.
        if (!onTextSelect) return;
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

        let marksToRender = [];

        if (viewMode === 'review') {
            redactions.forEach(r => {
                if (r.is_accepted) {
                    marksToRender.push({ ...r, mark_type: 'accepted' });
                    return;
                }
                if (!r.is_suggestion) return;
                const isPending = !r.is_accepted && !r.justification;
                const isRejected = !r.is_accepted && !!r.justification;
                if (isPending) {
                    marksToRender.push({ ...r, mark_type: 'suggestion' });
                } else if (isRejected && (!reviewComplete || r.id === hoveredSuggestionId)) {
                    marksToRender.push({ ...r, mark_type: 'rejected' });
                }
            });
            if (pendingRedaction) {
                marksToRender.push({
                    ...pendingRedaction,
                    id: 'pending-redaction',
                    mark_type: 'pending',
                });
            }
        } else {
            marksToRender = redactions.map(r => ({ ...r, mark_type: 'accepted' }));
        }

        const sortedMarks = marksToRender.sort((a, b) => a.start_char - b.start_char);
        let lastIndex = 0;
        const parts = [];

        sortedMarks.forEach((mark, index) => {
            const markStart = mark.start_char;
            const markEndExclusive = mark.end_char + 1;

            if (markStart > lastIndex) {
                parts.push(
                    <React.Fragment key={`text-${index}`}>
                        {text.substring(lastIndex, markStart)}
                    </React.Fragment>
                );
            }

            let style = {};
            const isHovered = mark.id === hoveredSuggestionId;
            const key = `${mark.id}-${index}`;

            if (viewMode === 'review' && mark.mark_type === 'pending') {
                style = { backgroundColor: 'rgba(255, 214, 10, 0.6)', borderRadius: '3px' };
            } else {
                style = getHighlightStyle(mark, isHovered, viewMode);
            }
            const markText = text.substring(markStart, markEndExclusive);

            parts.push(
                <Box
                    component="span"
                    sx={{
                        ...style,
                        cursor: viewMode === 'review' ? 'pointer' : 'default',
                    }}
                    key={key}
                    onClick={viewMode === 'review' && onHighlightClick ? () => onHighlightClick(mark.id) : undefined}
                >
                    {markText}
                </Box>
            );
            lastIndex = markEndExclusive;
        });

        if (lastIndex < text.length) {
            parts.push(<React.Fragment key="text-end">{text.substring(lastIndex)}</React.Fragment>);
        }
        return parts;
    };

    return (
        <Paper
            elevation={0}
            sx={{
                p: 4, lineHeight: 2, fontSize: '1.1rem', whiteSpace: 'pre-wrap',
                flexGrow: 1, overflowY: 'auto', height: '100%'
            }}
            ref={viewerRef}
            // Only attach mouseup listener if onTextSelect is provided (i.e., in review mode)
            onMouseUp={onTextSelect ? handleMouseUp : undefined}
        >
            {renderDocument()}
        </Paper>
    );
};
