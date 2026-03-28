"use client"

import React, { useEffect, useRef, useState } from 'react';
import { Alert, LinearProgress, Typography, Box } from '@mui/material';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { getTrainingStatus } from '@/services/trainingService';

export const TrainingStatusBanner = ({ pollInterval = 10000 }) => {
    const { data: session } = useSession();
    const router = useRouter();
    const [isRunning, setIsRunning] = useState(false);
    const wasRunningRef = useRef(false);

    useEffect(() => {
        if (!session?.access_token) return;

        const checkStatus = async () => {
            try {
                const { is_running } = await getTrainingStatus(session.access_token);
                if (wasRunningRef.current && !is_running) {
                    wasRunningRef.current = false;
                    setIsRunning(false);
                    router.refresh();
                } else {
                    wasRunningRef.current = is_running;
                    setIsRunning(is_running);
                }
            } catch (error) {
                console.error('Failed to poll training status:', error);
            }
        };

        checkStatus();
        const intervalId = setInterval(checkStatus, pollInterval);
        return () => clearInterval(intervalId);
    }, [session?.access_token, router, pollInterval]);

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
