"use client";

import React from 'react';
import { Container, Stack, Box, Typography, CircularProgress, Button } from '@mui/material';
import useSWR from 'swr';
import { useSession } from 'next-auth/react';
import NextLink from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import CaseInformation from './CaseInformation';
import CaseDocuments from './CaseDocuments';
import CaseExportManager from './CaseExportManager';
import apiClient from '@/api/apiClient';

const fetcher = (url, token) => apiClient.get(url, { headers: { Authorization: `Bearer ${token}` } }).then(res => res.data);

export default function CaseDetailClientPage({ initialCaseData }) {
    const { data: session } = useSession();
    const caseId = initialCaseData.id;

    // Use SWR for data fetching and automatic revalidation
    const { data: caseData, mutate } = useSWR(
        session ? [`/cases/${caseId}`, session.access_token] : null,
        ([url, token]) => fetcher(url, token),
        {
            fallbackData: initialCaseData,
            // Set up polling interval ONLY if the export is processing
            refreshInterval: (data) => (data?.export_status === 'PROCESSING' ? 5000 : 0),
        }
    );

    if (!caseData) {
        return <Container sx={{ textAlign: 'center', mt: 5 }}><CircularProgress /></Container>;
    }

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Stack direction="column" spacing={2}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Button
                        component={NextLink}
                        href="/cases"
                        variant="contained"
                        startIcon={<ArrowBackIcon />}
                    >
                        Back to Cases
                    </Button>
                    <CaseExportManager caseData={caseData} onUpdate={mutate} />
                </Box>
                <CaseInformation caseObject={caseData} onUpdate={mutate} />
                <CaseDocuments caseId={caseData.id} documents={caseData.documents} onUpdate={mutate} />
            </Stack>
        </Container>
    );
}