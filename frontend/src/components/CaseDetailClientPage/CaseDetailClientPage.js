"use client";

import React from 'react';
import { Container, Stack, Box, CircularProgress, Button } from '@mui/material';
import useSWR from 'swr';
import { useSession } from 'next-auth/react';
import NextLink from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import { CaseInformation } from '@/components/CaseInformation';
import { CaseDocuments } from '@/components/CaseDocuments';
import { CaseExportManager } from '@/components/CaseExportManager';
import { getCase } from '@/services/caseService';

export const CaseDetailClientPage = ({ initialCaseData }) => {
    const { data: session } = useSession();
    const caseId = initialCaseData.id;

    // Use SWR for data fetching and automatic revalidation
    const { data: caseData, mutate } = useSWR(
        session ? [`/cases/${caseId}`, session.access_token] : null,
        ([url, token]) => getCase(caseId, token),
        {
            fallbackData: initialCaseData,
            // Set up polling interval ONLY if the export is processing
            refreshInterval: (data) => (data?.export_status === 'PROCESSING' ? 5000 : 0),
        }
    );

    const handleMutate = React.useCallback(async () => {
        if (mutate) await mutate();
    }, [mutate]);

    if (!caseData) {
        return <Container sx={{ textAlign: 'center', mt: 5 }}><CircularProgress /></Container>;
    }

    const finalStatuses = ['COMPLETED', 'CLOSED', 'WITHDRAWN'];
    const isCaseFinalised = finalStatuses.includes(caseData.status);

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
                    <CaseExportManager caseData={caseData} onUpdate={handleMutate} />
                </Box>
                <CaseInformation caseObject={caseData} onUpdate={handleMutate} />
                <CaseDocuments
                    caseId={caseData.id}
                    documents={caseData.documents}
                    onUpdate={handleMutate}
                    isCaseFinalised={isCaseFinalised}
                />
            </Stack>
        </Container>
    );
}