"use client";

import React, { useState, useEffect, useRef } from 'react';
import { Box, Button, CircularProgress } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { createCaseExport } from '@/services/caseService';
import { useSession } from 'next-auth/react';
import toast from 'react-hot-toast';

export const CaseExportManager = ({ caseData, onUpdate }) => {
    const { data: session } = useSession();
    const [isProcessing, setIsProcessing] = useState(false);
    const prevExportStatusRef = useRef(caseData.export_status);

    const hasIncompleteDocuments = caseData.documents?.some(doc => doc.status !== 'Completed');
    const isButtonDisabled = caseData.documents === undefined ? true : isProcessing || caseData.export_status === 'PROCESSING' || caseData.documents.length === 0 || hasIncompleteDocuments;

    const handleGenerateExport = async () => {
        setIsProcessing(true);
        try {
            await createCaseExport(caseData.id, session.access_token);
            toast.success('Export generation started.', { id: 'export-toast' });
            // Trigger a re-fetch of the case data to get the 'PROCESSING' status
            if (onUpdate) onUpdate();
        } catch (error) {
            toast.error('Failed to start export process.', { id: 'export-toast' });
            setIsProcessing(false);
        }
    };

    useEffect(() => {
        const currentStatus = caseData.export_status;
        const prevStatus = prevExportStatusRef.current;

        // Update local processing state based on case data from server
        if (currentStatus === 'PROCESSING') {
            setIsProcessing(true);
        } else {
            setIsProcessing(false);
            // Only show a toast if the status has *changed* from processing to a final state.
            if (prevStatus === 'PROCESSING' && currentStatus === 'COMPLETED') {
                toast.success('Export package is ready for download.', { id: 'export-toast' });
            } else if (prevStatus === 'PROCESSING' && currentStatus === 'ERROR') {
                toast.error('There was an error generating the export.', { id: 'export-toast' });
            }
        }
        // Update the ref to the current status for the next render cycle.
        prevExportStatusRef.current = currentStatus;
    }, [caseData.export_status]);


    const renderContent = () => {
        switch (caseData.export_status) {
            case 'COMPLETED':
                return (
                    <Button
                        variant="contained"
                        color="success"
                        startIcon={<DownloadIcon />}
                        href={caseData.export_file}
                        download
                    >
                        Download Package
                    </Button>
                );
            case 'PROCESSING':
                return (
                    <Button variant="contained" disabled sx={{
                        minWidth: 220,
                        '&.Mui-disabled': {
                            backgroundColor: 'rgba(255, 255, 255, 0.12)',
                            color: 'rgba(255, 255, 255, 0.5)',
                        },
                    }}>
                        <CircularProgress size={24} sx={{ mr: 1 }} />
                        Generating Package...
                    </Button>
                );
            case 'ERROR':
                return (
                    <Button variant="contained" color="error" onClick={handleGenerateExport} disabled={isButtonDisabled}>
                        Retry Export
                    </Button>
                );
            case 'NONE':
            default:
                return (
                    <Button variant="contained" color="primary" onClick={handleGenerateExport} disabled={isButtonDisabled}>
                        Generate Disclosure Package
                    </Button>
                );
        }
    };

    return <Box>{renderContent()}</Box>;
}