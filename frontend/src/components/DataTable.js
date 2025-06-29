"use client"

import React from 'react'
import NextLink from 'next/link';
import Link from '@mui/material/Link';
import { DataGrid } from '@mui/x-data-grid/DataGrid';

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
    { field: 'status', headerName: 'Status', width: 150 },
    {
        field: 'created_at',
        headerName: 'Created At',
        width: 180,
        valueGetter: (params) => {
            const date = new Date(params).toLocaleDateString('en-GB');
            return date
        },
    },
];

export default function DataTable({ rows }) {
    return <DataGrid
        rows={rows}
        columns={columns}
        pageSize={10}
        rowsPerPageOptions={[10, 20, 50]}
        disableSelectionOnClick
        getRowId={(row) => row.id}

    />;
}
