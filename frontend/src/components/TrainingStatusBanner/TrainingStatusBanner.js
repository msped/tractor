"use client"

import React, { useEffect, useState } from 'react';
import { Alert, LinearProgress, Typography, Box } from '@mui/material';
import { useRouter } from 'next/navigation';
import { getTrainingStatus } from '@/services/trainingService';

export const TrainingStatusBanner = ({ initialIsRunning = false, pollInterval = 10000 }) => {
    const router = useRouter();
    const [isRunning, setIsRunning] = useState(initialIsRunning);

    // Only poll while a run is actually in progress. The initial state comes
    // from the server (page load), so an idle page makes no status requests;
    // polling exists solely to detect when the in-progress run finishes.
    useEffect(() => {
        if (!isRunning) return;

        let active = true;
        const checkStatus = async () => {
            try {
                const { is_running } = await getTrainingStatus();
                if (active && !is_running) {
                    setIsRunning(false);
                    router.refresh();
                }
            } catch (error) {
                console.error('Failed to poll training status:', error);
            }
        };

        const intervalId = setInterval(checkStatus, pollInterval);
        return () => {
            active = false;
            clearInterval(intervalId);
        };
    }, [isRunning, router, pollInterval]);

    if (!isRunning) return null;

    return (
        <Box sx={{ mb: 3 }}>
            <Alert severity="info" icon={false} sx={{ display: 'block' }}>
                <Typography variant="body2" sx={{ mb: 1 }}>
                    Training is in progress. This page will update automatically when complete.
                </Typography>
                <LinearProgress />
            </Alert>
        </Box>
    );
};
