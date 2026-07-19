"use client";

import React from 'react';
import useSWR from 'swr';
import {
    Box,
    Chip,
    CircularProgress,
    Divider,
    List,
    ListItem,
    ListItemText,
    Paper,
    Stack,
    Typography,
} from '@mui/material';

import { getCaseDisclosureDiff } from '@/services/caseService';

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
 * Shows what a review changed by presenting the diff between the case's latest
 * disclosure snapshot and the current live redaction state — added, removed and
 * modified redactions grouped by change type. Mounted only for disclosed cases;
 * a legacy disclosed case with no snapshot (the endpoint 404s) collapses to a
 * quiet unavailable note.
 */
export const CaseDisclosureDiff = ({ caseData }) => {
    const caseId = caseData?.id;
    const { data: diff, error } = useSWR(
        caseId
            ? [`/cases/${caseId}/diff`, caseData.status, caseData.export_status]
            : null,
        () => getCaseDisclosureDiff(caseId)
    );

    const totalChanges =
        diff &&
        diff.counts.added + diff.counts.removed + diff.counts.modified;

    return (
        <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
                Changes Since Last Disclosure
            </Typography>
            <Divider />
            {error ? (
                <Box sx={{ py: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                        The disclosure diff is unavailable for this case.
                    </Typography>
                </Box>
            ) : !diff ? (
                <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}>
                    <CircularProgress size={24} />
                </Box>
            ) : (
                <Box sx={{ pt: 1 }}>
                    <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                    >
                        {diff.snapshot.export
                            ? `Compared against “${diff.snapshot.export.label}”.`
                            : 'Compared against the last disclosure snapshot.'}
                    </Typography>
                    {totalChanges === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                            No changes since the last disclosure.
                        </Typography>
                    ) : (
                        SECTIONS.filter(
                            (section) => diff[section.key].length > 0
                        ).map((section) => (
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
                                    <Typography
                                        variant="body2"
                                        color="text.secondary"
                                    >
                                        {diff[section.key].length}
                                    </Typography>
                                </Stack>
                                <List dense disablePadding>
                                    {diff[section.key].map((entry) => (
                                        <ListItem
                                            key={entry.id}
                                            divider
                                            disableGutters
                                        >
                                            <ListItemText
                                                primary={truncate(entry.text)}
                                                secondary={
                                                    <>
                                                        {entrySecondary(entry)}
                                                        {section.key ===
                                                            'modified' && (
                                                            <ChangeLines
                                                                changes={
                                                                    entry.changes
                                                                }
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
                        ))
                    )}
                </Box>
            )}
        </Paper>
    );
};
