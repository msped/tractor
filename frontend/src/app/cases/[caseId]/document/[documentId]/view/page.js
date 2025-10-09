import apiClient from '@/api/apiClient';
import React from 'react';
import { auth } from '@/auth';
import { redirect } from 'next/navigation';
import { DocumentViewComponent } from '@/components/DocumentViewComponent';
import { Box, Alert } from '@mui/material';

export default async function page({ params }) {
    const { caseId, documentId } = await params;
    const session = await auth();

    if (!session) {
        redirect('/');
    }

    let documentData = null;
    let redactions = [];
    let fetchError = null;
    
    try {
        const docResponse = await apiClient.get(`cases/documents/${documentId}`, {
            headers: {
                Authorization: `Bearer ${session.access_token}`,
            },
        });

        documentData = docResponse.data;
        const allRedactions = documentData.redactions || [];

        // For the view page, we only care about redactions that have been confirmed.
        // These are either AI suggestions that were accepted, or manual redactions.
        redactions = allRedactions.filter(r => r.is_accepted || !r.is_suggestion);

    } catch (error) {
        if (error.response?.status === 401) {
            redirect('/');
        }
        console.error("Failed to fetch document for view:", error);
        fetchError = "There was an issue retrieving the document. Please try again later.";
    }

    if (fetchError) {
        return (
            <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <Alert severity="error">{fetchError}</Alert>
            </Box>
        );
    }

    return <DocumentViewComponent caseId={caseId} document={documentData} redactions={redactions} />;
}
