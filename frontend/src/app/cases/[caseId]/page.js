import React from 'react'
import apiClient from '@/api/apiClient';
import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { Container, Stack } from '@mui/material';

import CaseInformation from '@/components/CaseInformation';
import CaseDocuments from '@/components/CaseDocuments';

export default async function page({ params }) {
    const { caseId } = await params;
    const session = await auth();

    let caseFile = null;
    let fetchError = null;

    try {
        caseFile = await apiClient.get(`cases/${caseId}`, {
            headers: {
                Authorization: `Bearer ${session.access_token}`,
            },
        }).then(response => response.data)
    } catch (error) {
        if (error.response?.status === 401) {
            redirect('/');
        }
        console.error("Failed to fetch cases:", error);
        fetchError = "There was an issue retrieving your cases. Please try again later.";
    }

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Stack direction="column" spacing={2}>
                <CaseInformation caseObject={caseFile} />
                <CaseDocuments caseId={id} documents={caseFile?.documents}/>
            </Stack>
        </Container>
    )
}
