"use client"

import React from 'react'
import NextLink from 'next/link';
import Link from '@mui/material/Link';
import Button from '@mui/material/Button';
import { styled } from '@mui/material/styles';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import CancelIcon from '@mui/icons-material/Cancel';
import SearchIcon from '@mui/icons-material/Search';
import Tooltip from '@mui/material/Tooltip';
import Chip from '@mui/material/Chip';
import {
    DataGrid,
    Toolbar,
    ToolbarButton,
    QuickFilter,
    QuickFilterControl,
    QuickFilterClear,
    QuickFilterTrigger,
    useGridApiContext,
    useGridSelector,
    gridFilterModelSelector,
} from '@mui/x-data-grid';
import { Box } from '@mui/system';
import AddIcon from '@mui/icons-material/Add';

const openInProgressValues = ['OPEN', 'IN_PROGRESS', 'UNDER_REVIEW'];
const completedClosedValues = ['COMPLETED', 'CLOSED'];
const withdrawnValues = ['WITHDRAWN'];

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

const StyledQuickFilter = styled(QuickFilter)({
    display: 'grid',
    alignItems: 'center',
    marginLeft: 'auto',
});

const StyledToolbarButton = styled(ToolbarButton)(({ theme, ownerState }) => ({
    gridArea: '1 / 1',
    width: 'min-content',
    height: 'min-content',
    zIndex: 1,
    opacity: ownerState.expanded ? 0 : 1,
    pointerEvents: ownerState.expanded ? 'none' : 'auto',
    transition: theme.transitions.create(['opacity']),
}));

const StyledTextField = styled(TextField)(({ theme, ownerState }) => ({
    gridArea: '1 / 1',
    overflowX: 'clip',
    width: ownerState.expanded ? 260 : 'var(--trigger-width)',
    opacity: ownerState.expanded ? 1 : 0,
    transition: theme.transitions.create(['width', 'opacity']),
}));

function CustomToolbar() {
    const apiRef = useGridApiContext();
    const filterModel = useGridSelector(apiRef, gridFilterModelSelector);

    const statusFilter = filterModel.items.find((item) => item.field === 'status');
    const activeFilterValues = statusFilter?.value || [];

    const isFilterActive = (values) => JSON.stringify(activeFilterValues.sort()) === JSON.stringify(values.sort());

    const handleFilterChange = (values) => {
        const otherFilters = filterModel.items.filter(
            (item) => item.field !== 'status',
        );

        const newFilterItems = [...otherFilters];

        if (values && values.length > 0) {
            newFilterItems.push({ field: 'status', operator: 'isAnyOf', value: values });
        }

        apiRef.current.setFilterModel({ items: newFilterItems });
    }

    return (
        <Toolbar>
            <Button size="small" onClick={() => handleFilterChange([])} variant={activeFilterValues.length === 0 ? 'contained' : 'text'}>
                All
            </Button>
            <Button size="small" onClick={() => handleFilterChange(openInProgressValues)} variant={isFilterActive(openInProgressValues) ? 'contained' : 'text'}>
                Open / In Progress
            </Button>
            <Button size="small" onClick={() => handleFilterChange(completedClosedValues)} variant={isFilterActive(completedClosedValues) ? 'contained' : 'text'}>
                Completed / Closed
            </Button>
            <Button size="small" onClick={() => handleFilterChange(withdrawnValues)} variant={isFilterActive(withdrawnValues) ? 'contained' : 'text'}>
                Withdrawn
            </Button>
            <Box sx={{ flexGrow: 1 }} />
            <Button
                size="small"
                variant="contained"
                startIcon={<AddIcon />}
                component={NextLink}
                href="/cases/new"
                passHref
                sx={{ marginRight: 1 }}
            >
                New Case
            </Button>
            <StyledQuickFilter defaultExpanded>
                <QuickFilterTrigger
                    render={(triggerProps, state) => (
                        <Tooltip title="Search" enterDelay={0}>
                            <StyledToolbarButton
                                {...triggerProps}
                                ownerState={{ expanded: state.expanded }}
                                color="default"
                                aria-disabled={state.expanded}
                            >
                                <SearchIcon fontSize="small" />
                            </StyledToolbarButton>
                        </Tooltip>
                    )}
                />
                <QuickFilterControl
                    render={({ ref, ...controlProps }, state) => (
                        <StyledTextField
                            {...controlProps}
                            ownerState={{ expanded: state.expanded }}
                            inputRef={ref}
                            aria-label="Search"
                            placeholder="Search..."
                            size="small"
                            slotProps={{
                                input: {
                                    startAdornment: (
                                        <InputAdornment position="start">
                                            <SearchIcon fontSize="small" />
                                        </InputAdornment>
                                    ),
                                    endAdornment: state.value ? (
                                        <InputAdornment position="end">
                                            <QuickFilterClear
                                                edge="end"
                                                size="small"
                                                aria-label="Clear search"
                                                material={{ sx: { marginRight: -0.75 } }}
                                            >
                                                <CancelIcon fontSize="small" />
                                            </QuickFilterClear>
                                        </InputAdornment>
                                    ) : null,
                                ...controlProps.slotProps?.input,
                                },
                                ...controlProps.slotProps,
                            }}
                        />
                    )}
                />
            </StyledQuickFilter>
        </Toolbar>
    );
}

export const DataTable = ({ rows }) => {
    return <DataGrid
        rows={rows}
        columns={columns}
        pageSize={10}
        rowsPerPageOptions={[10, 20, 50]}
        disableSelectionOnClick
        getRowId={(row) => row.id}
        slots={{ toolbar: CustomToolbar }}
        showToolbar
        initialState={{
            filter: {
                filterModel: {
                    items: [
                        {
                            field: 'status',
                            operator: 'isAnyOf',
                            value: openInProgressValues,
                        },
                    ],
                },
            },
        }}
        sx={{ height: '100%', width: '100%' }}
    />;
}
