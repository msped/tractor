import { useState, useCallback, useEffect, useMemo } from 'react';
import { mergeAdjacentSpans, groupByTextAndType } from '@/utils/mergeRedactionSpans';

export function useRedactionDisplay({ redactions }) {
    const [splitMerges, setSplitMerges] = useState(new Set());
    const [hoveredSuggestionId, setHoveredSuggestionId] = useState(null);
    const [scrollToId, setScrollToId] = useState(null);
    const [scrollToDocumentId, setScrollToDocumentId] = useState(null);

    useEffect(() => {
        if (!scrollToDocumentId) return;
        const el = window.document.querySelector(`[data-redaction-id="${scrollToDocumentId}"]`);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        setScrollToDocumentId(null);
    }, [scrollToDocumentId]);

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

    const handleCardClick = useCallback((redactionId) => {
        setScrollToDocumentId(redactionId);
    }, []);

    return {
        displaySections,
        splitMerges,
        setSplitMerges,
        hoveredSuggestionId,
        scrollToId,
        setScrollToId,
        handleSuggestionMouseEnter,
        handleSuggestionMouseLeave,
        handleHighlightClick,
        handleRemoveScrollId,
        handleCardClick,
    };
}
