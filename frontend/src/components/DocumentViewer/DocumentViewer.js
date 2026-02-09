import React, { useRef, useMemo } from 'react';
import { Paper, Box, Typography } from '@mui/material';

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

// Use proportional font for document body
const fontFamily = '"Georgia", "Times New Roman", serif';

// Heading styles based on level, scaled by baseFontSize
const getHeadingStyles = (baseFontSize) => ({
    1: { fontSize: `${1.8 * baseFontSize}rem`, fontWeight: 'bold', marginTop: '1.5em', marginBottom: '0.5em' },
    2: { fontSize: `${1.5 * baseFontSize}rem`, fontWeight: 'bold', marginTop: '1.2em', marginBottom: '0.4em' },
    3: { fontSize: `${1.2 * baseFontSize}rem`, fontWeight: 'bold', marginTop: '1em', marginBottom: '0.3em' },
    4: { fontSize: `${1.1 * baseFontSize}rem`, fontWeight: 'bold', marginTop: '0.8em', marginBottom: '0.3em' },
    5: { fontSize: `${1.0 * baseFontSize}rem`, fontWeight: 'bold', marginTop: '0.6em', marginBottom: '0.2em' },
    6: { fontSize: `${0.9 * baseFontSize}rem`, fontWeight: 'bold', marginTop: '0.5em', marginBottom: '0.2em' },
});

const paragraphStyles = {
    marginBottom: '1em',
    textAlign: 'left',
    lineHeight: 1.8,
};

const getTableStyles = (hasBorders, currentFontSize) => ({
    overflowX: 'auto',
    margin: '1em 0',
    whiteSpace: 'normal',
    '& table': {
        borderCollapse: 'collapse',
        width: '100%',
        fontFamily: fontFamily,
        fontSize: currentFontSize,
    },
    '& th, & td': {
        ...(hasBorders ? { border: '1px solid #ddd' } : {}),
        padding: '6px 8px',
        textAlign: 'left',
        wordBreak: 'break-word',
    },
    '& th': {
        backgroundColor: '#f2f2f2',
        fontWeight: 'bold',
        whiteSpace: 'nowrap',
    },
});

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

/**
 * Build a sorted list of table regions from the tables array.
 * Each table has ner_start/ner_end marking its position in extracted_text.
 */
const buildTableRegions = (tables) => {
    if (!tables || tables.length === 0) return [];
    return tables
        .filter(t => t.ner_start != null && t.ner_end != null)
        .sort((a, b) => a.ner_start - b.ner_start);
};

/**
 * Render a text segment, replacing any table regions with HTML tables.
 * segStart is the absolute character position of this segment in extracted_text.
 * renderedTables tracks which tables have already been rendered to avoid duplicates.
 */
const renderSegmentWithTables = (segText, segStart, tableRegions, parts, keyPrefix, renderedTables, scaledFontSize) => {
    let cursor = segStart;
    const segEnd = segStart + segText.length;
    let partIndex = 0;

    for (const table of tableRegions) {
        // Skip tables that are entirely before this segment
        if (table.ner_end <= cursor) continue;
        // Stop if table starts after this segment
        if (table.ner_start >= segEnd) break;

        // Skip if this table was already rendered
        if (renderedTables.has(table.id)) {
            cursor = Math.min(table.ner_end, segEnd);
            continue;
        }

        // Render text before this table
        if (table.ner_start > cursor) {
            const beforeText = segText.substring(cursor - segStart, table.ner_start - segStart);
            parts.push(
                <React.Fragment key={`${keyPrefix}-text-${partIndex}`}>
                    {beforeText}
                </React.Fragment>
            );
            partIndex++;
        }

        // Render the HTML table and mark as rendered
        parts.push(
            <Box
                key={`${keyPrefix}-table-${table.id}`}
                component="div"
                sx={getTableStyles(table.hasBorders !== false, scaledFontSize)}
                dangerouslySetInnerHTML={{ __html: table.html }}
            />
        );
        renderedTables.add(table.id);
        partIndex++;

        cursor = Math.min(table.ner_end, segEnd);
    }

    // Render remaining text after last table
    if (cursor < segEnd) {
        const remaining = segText.substring(cursor - segStart);
        parts.push(
            <React.Fragment key={`${keyPrefix}-text-${partIndex}`}>
                {remaining}
            </React.Fragment>
        );
    }
};

/**
 * Render text content with redaction highlights applied.
 * Returns an array of React elements with highlights for marks that fall within the text range.
 */
const renderTextWithHighlights = (elementText, elementStart, sortedMarks, hoveredSuggestionId, viewMode, onHighlightClick) => {
    const elementEnd = elementStart + elementText.length;
    const parts = [];
    let cursor = 0;

    // Find marks that overlap with this element
    const relevantMarks = sortedMarks.filter(mark =>
        mark.start_char < elementEnd && mark.end_char > elementStart
    );

    relevantMarks.forEach((mark, index) => {
        // Calculate local positions within this element
        const localStart = Math.max(0, mark.start_char - elementStart);
        const localEnd = Math.min(elementText.length, mark.end_char - elementStart);

        // Add text before this mark
        if (localStart > cursor) {
            parts.push(
                <React.Fragment key={`text-${index}`}>
                    {elementText.substring(cursor, localStart)}
                </React.Fragment>
            );
        }

        // Add the highlighted mark
        const isHovered = mark.id === hoveredSuggestionId;
        let style = {};
        if (viewMode === 'review' && mark.mark_type === 'pending') {
            style = { backgroundColor: 'rgba(255, 214, 10, 0.6)', borderRadius: '3px' };
        } else {
            style = getHighlightStyle(mark, isHovered, viewMode);
        }

        parts.push(
            <Box
                component="span"
                sx={{
                    ...style,
                    cursor: viewMode === 'review' ? 'pointer' : 'default',
                }}
                key={`mark-${mark.id}-${index}`}
                onClick={viewMode === 'review' && onHighlightClick ? () => onHighlightClick(mark.id) : undefined}
            >
                {elementText.substring(localStart, localEnd)}
            </Box>
        );
        cursor = localEnd;
    });

    // Add remaining text after last mark
    if (cursor < elementText.length) {
        parts.push(
            <React.Fragment key="text-end">
                {elementText.substring(cursor)}
            </React.Fragment>
        );
    }

    return parts.length > 0 ? parts : elementText;
};

export const DocumentViewer = ({ text, tables, structure, redactions, pendingRedaction, hoveredSuggestionId, onTextSelect, onHighlightClick, reviewComplete, viewMode = 'review', baseFontSize = 1 }) => {
    const viewerRef = useRef(null);
    const tableRegions = useMemo(() => buildTableRegions(tables), [tables]);
    const scaledFontSize = `${baseFontSize}rem`;
    const headingStyles = useMemo(() => getHeadingStyles(baseFontSize), [baseFontSize]);

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

    // Build marks to render based on view mode
    const sortedMarks = useMemo(() => {
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

        return marksToRender.sort((a, b) => a.start_char - b.start_char);
    }, [redactions, pendingRedaction, viewMode, reviewComplete, hoveredSuggestionId]);

    // Render structured document with headings, paragraphs, and tables
    const renderStructuredDocument = () => {
        if (!structure || structure.length === 0) return null;

        return structure.map((element, index) => {
            if (element.type === 'heading') {
                const level = element.level || 1;
                const hStyle = headingStyles[level] || headingStyles[1];
                const HeadingTag = `h${Math.min(level, 6)}`;

                return (
                    <Typography
                        key={`heading-${index}`}
                        component={HeadingTag}
                        sx={{
                            ...hStyle,
                            fontFamily: fontFamily,
                        }}
                    >
                        {renderTextWithHighlights(element.text, element.start, sortedMarks, hoveredSuggestionId, viewMode, onHighlightClick)}
                    </Typography>
                );
            }

            if (element.type === 'paragraph') {
                return (
                    <Typography
                        key={`para-${index}`}
                        component="p"
                        sx={{
                            ...paragraphStyles,
                            fontFamily: fontFamily,
                            fontSize: scaledFontSize,
                        }}
                    >
                        {renderTextWithHighlights(element.text, element.start, sortedMarks, hoveredSuggestionId, viewMode, onHighlightClick)}
                    </Typography>
                );
            }

            if (element.type === 'table') {
                // Find the table data by id
                const tableData = tables?.find(t => t.id === element.table_id);
                if (!tableData) return null;

                // If we have cell data, render with React for highlighting support
                if (tableData.cells && tableData.cells.length > 0) {
                    // Group cells by row
                    const rowMap = new Map();
                    tableData.cells.forEach(cell => {
                        if (!rowMap.has(cell.row)) {
                            rowMap.set(cell.row, []);
                        }
                        rowMap.get(cell.row).push(cell);
                    });

                    // Sort rows and cells within rows
                    const sortedRows = Array.from(rowMap.entries())
                        .sort((a, b) => a[0] - b[0])
                        .map(([, cells]) => cells.sort((a, b) => a.col - b.col));

                    const hasBorders = tableData.hasBorders !== false;
                    return (
                        <Box key={`table-${element.table_id}`} component="div" sx={getTableStyles(hasBorders, scaledFontSize)}>
                            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                                <tbody>
                                    {sortedRows.map((rowCells, rowIndex) => (
                                        <tr key={`row-${rowIndex}`}>
                                            {rowCells.map((cell, cellIndex) => (
                                                <td
                                                    key={`cell-${rowIndex}-${cellIndex}`}
                                                    style={{
                                                        ...(hasBorders ? { border: '1px solid #000' } : {}),
                                                        padding: '6px 8px',
                                                        backgroundColor: cell.bgColor || undefined,
                                                    }}
                                                >
                                                    {renderTextWithHighlights(
                                                        cell.text,
                                                        cell.start,
                                                        sortedMarks,
                                                        hoveredSuggestionId,
                                                        viewMode,
                                                        onHighlightClick
                                                    )}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </Box>
                    );
                }

                // Fallback to HTML rendering if no cell data
                if (tableData.html) {
                    return (
                        <Box
                            key={`table-${element.table_id}`}
                            component="div"
                            sx={getTableStyles(tableData.hasBorders !== false, scaledFontSize)}
                            dangerouslySetInnerHTML={{ __html: tableData.html }}
                        />
                    );
                }
                return null;
            }

            return null;
        });
    };

    // Render plain text document (fallback for non-DOCX files)
    const renderPlainDocument = () => {
        if (!text) return null;

        let lastIndex = 0;
        const parts = [];
        const renderedTables = new Set();

        sortedMarks.forEach((mark, index) => {
            const markStart = mark.start_char;
            const markEndExclusive = mark.end_char;

            if (markStart > lastIndex) {
                const segment = text.substring(lastIndex, markStart);
                renderSegmentWithTables(segment, lastIndex, tableRegions, parts, `pre-${index}`, renderedTables, scaledFontSize);
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
            const remaining = text.substring(lastIndex);
            renderSegmentWithTables(remaining, lastIndex, tableRegions, parts, 'end', renderedTables, scaledFontSize);
        }
        return parts;
    };

    // Use structured rendering if structure is available, otherwise fall back to plain text
    const hasStructure = structure && structure.length > 0;

    return (
        <Paper
            elevation={0}
            sx={{
                px: 3,
                py: 4,
                lineHeight: 1.6,
                fontSize: scaledFontSize,
                whiteSpace: hasStructure ? 'normal' : 'pre-wrap',
                fontFamily: fontFamily,
                flexGrow: 1,
                overflowY: 'auto',
                height: '100%',
            }}
            ref={viewerRef}
            // Only attach mouseup listener if onTextSelect is provided (i.e., in review mode)
            onMouseUp={onTextSelect ? handleMouseUp : undefined}
        >
            {hasStructure ? renderStructuredDocument() : renderPlainDocument()}
        </Paper>
    );
};
