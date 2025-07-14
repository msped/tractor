import React from 'react'
import apiClient from '@/api/apiClient';
import { auth } from "@/auth"

import RedactionReviewPage from '@/components/RedactionComponent';

export default async function page({ params }) {
    const { caseId, documentId } = await params;
    const session = await auth();

    let documentFile = null;
    let fetchError = null;
    
    try {
        documentFile = await apiClient.get(`cases/${caseId}/document/${documentId}/review`, {
            headers: {
                Authorization: `Bearer ${session.access_token}`,
            },
        }).then(response => response.data)
    } catch (error) {
        if (error.response?.status === 401) {
            redirect('/');
        }
        console.error("Failed to fetch document for review:", error);
        fetchError = "There was an issue retrieving the document for review. Please try again later.";
    }

    return <RedactionReviewPage
        document={documentFile}
        initialRedactions={documentFile?.redactions || []}
    />
}
