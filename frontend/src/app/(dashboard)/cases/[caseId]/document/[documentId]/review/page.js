import React from 'react'
import { auth } from "@/auth"
import { redirect } from 'next/navigation';
import { getDocumentForReview } from '@/services/documentService';

import { RedactionComponent } from '@/components/RedactionComponent';

export default async function page({ params }) {
    const { caseId, documentId } = await params;
    const session = await auth();

    if (!session) {
        redirect('/');
    }

    let documentFile = null;
    let fetchError = null;

    try {
        documentFile = await getDocumentForReview(caseId, documentId, session.access_token);
    } catch (error) {
        console.error("Failed to fetch document for review:", error);
        fetchError = "There was an issue retrieving the document for review. Please try again later.";
    }

    return <RedactionComponent
        document={documentFile}
        initialRedactions={documentFile?.redactions || []}
    />
}
