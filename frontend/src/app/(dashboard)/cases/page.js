import React from 'react'
import { Box, Typography, Container } from '@mui/material';
import { getCases } from '@/services/caseService';

import { DataTable } from '@/components/DataTable';

export default async function page() {
    let cases = [];
    let fetchError = null;

    try {
        cases = await getCases();
    } catch (error) {
        console.error("Failed to fetch cases:", error);
        fetchError = "There was an issue retrieving your cases. Please try again later.";
    }

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ height: 600, width: '100%', my: 4 }}>
                {fetchError ? (
                    <Typography color="error">{fetchError}</Typography>
                ) : (
                    <DataTable rows={cases}/>
                )}
            </Box>
        </Container>
    )
}
