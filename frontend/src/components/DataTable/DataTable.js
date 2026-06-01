"use client"

import React, { useState, useEffect } from 'react'
import NextLink from 'next/link';
import Link from '@mui/material/Link';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import IconButton from '@mui/material/IconButton';
import CancelIcon from '@mui/icons-material/Cancel';
import SearchIcon from '@mui/icons-material/Search';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { DataGrid, Toolbar } from '@mui/x-data-grid';
import { Box } from '@mui/system';
import { getCases } from '@/services/caseService';

const OPEN_IN_PROGRESS = ['OPEN', 'IN_PROGRESS', 'UNDER_REVIEW'];
const COMPLETED_CLOSED = ['COMPLETED', 'CLOSED'];
const WITHDRAWN = ['WITHDRAWN'];
const MIN_SEARCH_LENGTH = 3;
const SEARCH_DEBOUNCE_MS = 300;

const getStatusChipColor = (status) => {
    switch (status) {
        case 'OPEN':
        case 'IN_PROGRESS':
        case 'UNDER_REVIEW':
            return 'primary';
        case 'COMPLETED':
        case 'CLOSED':
            return 'success';
        case 'WITHDRAWN':
            return 'default';
        case 'ERROR':
            return 'error';
        default:
            return 'default';
    }
};

const columns = [
    {
        field: 'case_reference',
        headerName: 'Case Reference',
        width: 150,
        renderCell: (params) => (
            <Link component={NextLink} href={`/cases/${params.row.id}`} passHref>
                {params.value}
            </Link>
        ),
    },
    { field: 'data_subject_name', headerName: 'Subject Name', flex: 1, minWidth: 200 },
    {
        field: 'status',
        headerName: 'Status',
        width: 150,
        renderCell: (params) => (
            <Chip
                label={params.row.status_display || params.value}
                color={getStatusChipColor(params.value)}
                size="small" />
        )
    },
    {
        field: 'created_at',
        headerName: 'Created At',
        width: 180,
        valueGetter: (params) => new Date(params).toLocaleDateString('en-GB'),
    },
];

function CustomToolbar({ statusFilter, onStatusChange, search, onSearchChange }) {
    const isFilterActive = (values) =>
        JSON.stringify([...statusFilter].sort()) === JSON.stringify([...values].sort());

    return (
        <Toolbar>
            <Button size="small" onClick={() => onStatusChange([])} variant={statusFilter.length === 0 ? 'contained' : 'text'}>
                All
            </Button>
            <Button size="small" onClick={() => onStatusChange(OPEN_IN_PROGRESS)} variant={isFilterActive(OPEN_IN_PROGRESS) ? 'contained' : 'text'}>
                Open / In Progress
            </Button>
            <Button size="small" onClick={() => onStatusChange(COMPLETED_CLOSED)} variant={isFilterActive(COMPLETED_CLOSED) ? 'contained' : 'text'}>
                Completed / Closed
            </Button>
            <Button size="small" onClick={() => onStatusChange(WITHDRAWN)} variant={isFilterActive(WITHDRAWN) ? 'contained' : 'text'}>
                Withdrawn
            </Button>
            <Box sx={{ flexGrow: 1 }} />
            <TextField
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Search..."
                size="small"
                inputProps={{ 'aria-label': 'Search' }}
                slotProps={{
                    input: {
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon fontSize="small" />
                            </InputAdornment>
                        ),
                        endAdornment: search ? (
                            <InputAdornment position="end">
                                <IconButton
                                    edge="end"
                                    size="small"
                                    aria-label="Clear search"
                                    onClick={() => onSearchChange('')}
                                    sx={{ marginRight: -0.75 }}
                                >
                                    <CancelIcon fontSize="small" />
                                </IconButton>
                            </InputAdornment>
                        ) : null,
                    },
                }}
                sx={{ width: 260 }}
            />
        </Toolbar>
    );
}

export const DataTable = () => {
    const [rows, setRows] = useState([]);
    const [rowCount, setRowCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });
    const [statusFilter, setStatusFilter] = useState(OPEN_IN_PROGRESS);
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');

    useEffect(() => {
        if (search.length > 0 && search.length < MIN_SEARCH_LENGTH) return;
        const timer = setTimeout(() => {
            setDebouncedSearch(search);
            setPaginationModel((prev) => ({ ...prev, page: 0 }));
        }, SEARCH_DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [search]);

    useEffect(() => {
        let cancelled = false;

        const fetchCases = async () => {
            setLoading(true);
            setError(null);
            try {
                const params = {
                    page: paginationModel.page + 1,
                    page_size: paginationModel.pageSize,
                };
                if (debouncedSearch) params.search = debouncedSearch;
                if (statusFilter.length > 0) params.status = statusFilter.join(',');

                const data = await getCases(params);
                if (!cancelled) {
                    setRows(data.results);
                    setRowCount(data.count);
                }
            } catch {
                if (!cancelled) setError('Failed to load cases. Please try again.');
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchCases();
        return () => { cancelled = true; };
    }, [paginationModel, debouncedSearch, statusFilter]);

    const handleStatusChange = (values) => {
        setStatusFilter(values);
        setPaginationModel((prev) => ({ ...prev, page: 0 }));
    };

    const handleSearchChange = (value) => {
        setSearch(value);
    };

    if (error) {
        return <Typography color="error">{error}</Typography>;
    }

    return (
        <DataGrid
            rows={rows}
            columns={columns}
            rowCount={rowCount}
            loading={loading}
            paginationMode="server"
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            pageSizeOptions={[10, 25, 50]}
            disableSelectionOnClick
            getRowId={(row) => row.id}
            slots={{ toolbar: CustomToolbar }}
            slotProps={{
                toolbar: {
                    statusFilter,
                    onStatusChange: handleStatusChange,
                    search,
                    onSearchChange: handleSearchChange,
                },
            }}
            showToolbar
            sx={{ height: '100%', width: '100%' }}
        />
    );
};
