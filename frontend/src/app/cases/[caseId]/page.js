import React from 'react'
import apiClient from '@/api/apiClient';
import { auth } from "@/auth"
import { redirect } from "next/navigation"
import { Box, Alert } from '@mui/material';
import CaseDetailClientPage from '@/components/CaseDetailClientPage';

export default async function page({ params }) {
    const { caseId } = await params;
    const session = await auth();

    if (!session) {
        redirect('/');
    }

    let initialCaseData = null;
    let fetchError = null;

    try {
        const caseResponse = await apiClient.get(`cases/${caseId}`, {
            headers: {
                Authorization: `Bearer ${session.access_token}`,
            },
        });
        initialCaseData = caseResponse.data;
    } catch (error) {
        if (error.response?.status === 401) {
            redirect('/');
        }
        console.error("Failed to fetch case details:", error);
        fetchError = "There was an issue retrieving the case details. Please try again later.";
    }

    if (fetchError) {
        return (
            <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <Alert severity="error">{fetchError}</Alert>
            </Box>
        );
    }

    return <CaseDetailClientPage initialCaseData={initialCaseData} />;
}
