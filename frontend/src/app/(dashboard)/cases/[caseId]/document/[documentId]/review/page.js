import React from 'react'
import { getDocumentForReview } from '@/services/documentService';

import { RedactionComponent } from '@/components/RedactionComponent';

export default async function page({ params }) {
    const { caseId, documentId } = await params;

    let documentFile = null;
    let fetchError = null;

    try {
        documentFile = await getDocumentForReview(caseId, documentId);
    } catch (error) {
        console.error("Failed to fetch document for review:", error);
        fetchError = "There was an issue retrieving the document for review. Please try again later.";
    }

    return <RedactionComponent
        document={documentFile}
        initialRedactions={documentFile?.redactions || []}
    />
}
