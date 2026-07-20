"use client";

import React from 'react';
import {
    Box,
    Chip,
    List,
    ListItem,
    ListItemText,
    Stack,
    Typography,
} from '@mui/material';

const TYPE_LABELS = {
    OP_DATA: 'Operational',
    PII: 'Third-party PII',
    DS_INFO: 'Data subject',
};

const FIELD_LABELS = {
    start_char: 'Start',
    end_char: 'End',
    text: 'Text',
    redaction_type: 'Type',
    is_accepted: 'Decision',
    decided_by: 'Decided by',
    justification: 'Justification',
    context: 'Context',
};

const SECTIONS = [
    { key: 'added', label: 'Added', color: 'success' },
    { key: 'removed', label: 'Removed', color: 'error' },
    { key: 'modified', label: 'Modified', color: 'warning' },
];

const typeLabel = (value) => TYPE_LABELS[value] ?? value ?? '—';

const formatValue = (field, value) => {
    if (value === null || value === undefined || value === '') return '—';
    if (field === 'redaction_type') return typeLabel(value);
    if (field === 'is_accepted') return value ? 'Accepted' : 'Not accepted';
    return String(value);
};

const truncate = (text) => {
    if (!text) return '(empty)';
    return text.length > 80 ? `${text.slice(0, 80)}…` : text;
};

const entrySecondary = (entry) =>
    [entry.filename, typeLabel(entry.redaction_type)]
        .filter(Boolean)
        .join(' · ');

const ChangeLines = ({ changes }) => (
    <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
        {Object.entries(changes).map(([field, { from, to }]) => (
            <Typography
                key={field}
                variant="caption"
                component="span"
                sx={{ display: 'block' }}
            >
                {`${FIELD_LABELS[field] ?? field}: `}
                {formatValue(field, from)}
                {' → '}
                {formatValue(field, to)}
            </Typography>
        ))}
    </Box>
);

/**
 * Presentational renderer for a disclosure diff payload — the added, removed
 * and modified redactions between two disclosure states, grouped by change
 * type with per-field from→to lines for modifications. Purely display: it does
 * no fetching, so it is shared by the per-disclosure history rows and the
 * live "changes since last disclosure" preview shown during an open review.
 */
export const DisclosureDiffView = ({ diff }) => {
    if (!diff) return null;

    if (diff.baseline) {
        return (
            <Typography variant="body2" color="text.secondary">
                Original disclosure — nothing earlier to compare against.
            </Typography>
        );
    }

    const totalChanges =
        diff.counts.added + diff.counts.removed + diff.counts.modified;

    if (totalChanges === 0) {
        return (
            <Typography variant="body2" color="text.secondary">
                No redaction changes in this disclosure.
            </Typography>
        );
    }

    return (
        <Box>
            {SECTIONS.filter((section) => diff[section.key].length > 0).map(
                (section) => (
                    <Box key={section.key} sx={{ mb: 1.5 }}>
                        <Stack
                            direction="row"
                            spacing={1}
                            alignItems="center"
                            sx={{ mb: 0.5 }}
                        >
                            <Chip
                                label={section.label}
                                color={section.color}
                                size="small"
                            />
                            <Typography variant="body2" color="text.secondary">
                                {diff[section.key].length}
                            </Typography>
                        </Stack>
                        <List dense disablePadding>
                            {diff[section.key].map((entry) => (
                                <ListItem key={entry.id} divider disableGutters>
                                    <ListItemText
                                        primary={truncate(entry.text)}
                                        secondary={
                                            <>
                                                {entrySecondary(entry)}
                                                {section.key === 'modified' && (
                                                    <ChangeLines
                                                        changes={entry.changes}
                                                    />
                                                )}
                                            </>
                                        }
                                        secondaryTypographyProps={{
                                            component: 'span',
                                        }}
                                    />
                                </ListItem>
                            ))}
                        </List>
                    </Box>
                )
            )}
        </Box>
    );
};
