import React from 'react'
import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { Box, Typography, Container } from '@mui/material';
import apiClient from '@/api/apiClient';

import DataTable from '@/components/DataTable';

export default async function page() {
    const session = await auth();

    if (!session) {
        redirect("/");
    }

    let cases = [];
    let fetchError = null;

    try {
        cases = await apiClient.get('cases').then(response => response.data);
    } catch (error) {
        console.error("Failed to fetch cases:", error);
        fetchError = "There was an issue retrieving your cases. Please try again later.";
    }

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ textAlign: 'center', mb: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    Cases
                </Typography>
            </Box>
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
