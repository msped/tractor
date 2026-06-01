import React from 'react'
import { Box, Container } from '@mui/material';
import { DataTable } from '@/components/DataTable';

export default function page() {
    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ height: 600, width: '100%', my: 4 }}>
                <DataTable />
            </Box>
        </Container>
    )
}
