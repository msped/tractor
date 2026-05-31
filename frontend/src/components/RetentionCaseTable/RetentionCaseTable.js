"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import {
    Box,
    Button,
    Checkbox,
    FormControlLabel,
    FormGroup,
    IconButton,
    Popover,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';

const formatDate = (value) => {
    if (!value) return '—';
    const d = new Date(value);
    return isNaN(d) ? value : d.toLocaleDateString(undefined, { dateStyle: 'medium' });
};

const COLUMNS = [
    { key: 'case_reference', label: 'Case reference' },
    { key: 'data_subject_name', label: 'Name' },
    { key: 'data_subject_dob', label: 'Date of birth', render: formatDate },
    { key: 'retention_review_date', label: 'Retention date', render: formatDate },
    { key: 'created_at', label: 'Created date', render: formatDate },
    { key: 'status_display', label: 'Case outcome' },
];

const DEFAULT_VISIBLE = new Set(COLUMNS.map(c => c.key));

export const RetentionCaseTable = ({
    cases,
    selectedIds,
    onSelectionChange,
    onDeleteOne,
    onDeleteMany,
    isDeleting,
}) => {
    const [visibleColumns, setVisibleColumns] = useState(DEFAULT_VISIBLE);
    const [columnAnchor, setColumnAnchor] = useState(null);

    const allSelected = cases.length > 0 && cases.every(c => selectedIds.has(c.id));
    const someSelected = cases.some(c => selectedIds.has(c.id));

    const handleSelectAll = () => {
        const next = new Set(selectedIds);
        if (allSelected) {
            cases.forEach(c => next.delete(c.id));
        } else {
            cases.forEach(c => next.add(c.id));
        }
        onSelectionChange(next);
    };

    const handleSelectOne = (id) => {
        const next = new Set(selectedIds);
        if (next.has(id)) {
            next.delete(id);
        } else {
            next.add(id);
        }
        onSelectionChange(next);
    };

    const toggleColumn = (key) => {
        const next = new Set(visibleColumns);
        if (next.has(key)) {
            next.delete(key);
        } else {
            next.add(key);
        }
        setVisibleColumns(next);
    };

    const selectedInTable = cases.filter(c => selectedIds.has(c.id)).map(c => c.id);
    const visibleCols = COLUMNS.filter(c => visibleColumns.has(c.key));

    if (cases.length === 0) {
        return (
            <Typography variant="body2" color="text.secondary">
                No cases require review.
            </Typography>
        );
    }

    return (
        <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: 40, mb: 0.5 }}>
                <Tooltip title="Choose columns">
                    <IconButton size="small" onClick={(e) => setColumnAnchor(e.currentTarget)} aria-label="choose columns">
                        <ViewColumnIcon />
                    </IconButton>
                </Tooltip>
                <Box sx={{ visibility: someSelected ? 'visible' : 'hidden' }}>
                    <Button
                        variant="outlined"
                        color="error"
                        size="small"
                        startIcon={<DeleteIcon />}
                        onClick={() => onDeleteMany(selectedInTable)}
                        disabled={isDeleting}
                    >
                        Delete selected ({selectedInTable.length})
                    </Button>
                </Box>
            </Box>

            <Popover
                open={!!columnAnchor}
                anchorEl={columnAnchor}
                onClose={() => setColumnAnchor(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
            >
                <Box sx={{ p: 2 }}>
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>Columns</Typography>
                    <FormGroup>
                        {COLUMNS.map(col => (
                            <FormControlLabel
                                key={col.key}
                                control={
                                    <Checkbox
                                        checked={visibleColumns.has(col.key)}
                                        onChange={() => toggleColumn(col.key)}
                                        size="small"
                                    />
                                }
                                label={col.label}
                            />
                        ))}
                    </FormGroup>
                </Box>
            </Popover>

            <Table size="small">
                <TableHead>
                    <TableRow>
                        <TableCell padding="checkbox">
                            <Checkbox
                                indeterminate={someSelected && !allSelected}
                                checked={allSelected}
                                onChange={handleSelectAll}
                                inputProps={{ 'aria-label': 'select all' }}
                            />
                        </TableCell>
                        {visibleCols.map(col => (
                            <TableCell key={col.key}>{col.label}</TableCell>
                        ))}
                        <TableCell align="right">Actions</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {cases.map((c) => (
                        <TableRow key={c.id} selected={selectedIds.has(c.id)}>
                            <TableCell padding="checkbox">
                                <Checkbox
                                    checked={selectedIds.has(c.id)}
                                    onChange={() => handleSelectOne(c.id)}
                                    inputProps={{ 'aria-label': `select ${c.case_reference}` }}
                                />
                            </TableCell>
                            {visibleCols.map(col => (
                                <TableCell key={col.key}>
                                    {col.render ? col.render(c[col.key]) : (c[col.key] ?? '—')}
                                </TableCell>
                            ))}
                            <TableCell align="right">
                                <Tooltip title="Open in new tab">
                                    <IconButton
                                        component={Link}
                                        href={`/cases/${c.id}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        aria-label={`view ${c.case_reference}`}
                                    >
                                        <OpenInNewIcon />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title="Delete case">
                                    <IconButton
                                        color="error"
                                        onClick={() => onDeleteOne(c.id)}
                                        disabled={isDeleting}
                                        aria-label={`delete ${c.case_reference}`}
                                    >
                                        <DeleteIcon />
                                    </IconButton>
                                </Tooltip>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </Box>
    );
};
