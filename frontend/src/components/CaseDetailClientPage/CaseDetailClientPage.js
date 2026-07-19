"use client";

import React from 'react';
import { Container, Stack, Box, CircularProgress, Button } from '@mui/material';
import useSWR from 'swr';
import { useSession } from "@/contexts/SessionContext";
import toast from 'react-hot-toast';
import NextLink from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import { CaseInformation } from '@/components/CaseInformation';
import { CaseDocuments } from '@/components/CaseDocuments';
import { CaseExportManager } from '@/components/CaseExportManager';
import { CaseExportHistory } from '@/components/CaseExportHistory';
import { CaseDisclosureDiff } from '@/components/CaseDisclosureDiff';
import { CaseReviewBanner } from '@/components/CaseReviewBanner';
import { getCase } from '@/services/caseService';

export const CaseDetailClientPage = ({ initialCaseData }) => {
    const { session } = useSession();
    const caseId = initialCaseData.id;

    // Use SWR for data fetching and automatic revalidation
    const { data: caseData, mutate } = useSWR(
        session?.user?.id ? [`/cases/${caseId}`] : null,
        () => getCase(caseId),
        {
            fallbackData: initialCaseData,
            refreshInterval: (data) => (data?.export_status === 'PROCESSING' ? 5000 : 0),
            onError: () => toast.error('Failed to refresh case data. Please reload the page.'),
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
                <CaseReviewBanner caseData={caseData} onUpdate={handleMutate} />
                <CaseInformation caseObject={caseData} onUpdate={handleMutate} />
                <CaseDocuments
                    caseId={caseData.id}
                    documents={caseData.documents}
                    onUpdate={handleMutate}
                    isCaseFinalised={isCaseFinalised}
                    isUnderReview={caseData.status === 'UNDER_REVIEW'}
                />
                {caseData.is_disclosed && (
                    <CaseDisclosureDiff caseData={caseData} />
                )}
                <CaseExportHistory caseData={caseData} />
            </Stack>
        </Container>
    );
}