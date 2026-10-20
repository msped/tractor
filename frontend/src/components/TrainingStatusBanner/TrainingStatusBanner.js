"use client"

import React, { useEffect, useState } from 'react';
import { Alert, LinearProgress, Typography, Box, Button } from '@mui/material';
import { useRouter } from 'next/navigation';
import { getTrainingStatus, stopTraining } from '@/services/trainingService';
import toast from 'react-hot-toast';
import { toastError } from '@/api/toastError';

export const TrainingStatusBanner = ({ initialIsRunning = false, pollInterval = 10000 }) => {
    const router = useRouter();
    const [isRunning, setIsRunning] = useState(initialIsRunning);
    const [stopRequested, setStopRequested] = useState(false);
    const [stopping, setStopping] = useState(false);

    // Only poll while a run is actually in progress. The initial state comes
    // from the server (page load), so an idle page makes no status requests;
    // polling exists solely to detect when the in-progress run finishes.
    useEffect(() => {
        if (!isRunning) return;

        let active = true;
        const checkStatus = async () => {
            try {
                const { is_running, stop_requested } = await getTrainingStatus();
                if (!active) return;
                setStopRequested(Boolean(stop_requested));
                if (!is_running) {
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

    const handleStop = async () => {
        setStopping(true);
        try {
            await stopTraining();
            setStopRequested(true);
            toast.success('Stop requested. The run will finish shortly and no model will be saved.');
        } catch (error) {
            toastError(error, 'Failed to stop training. Please try again.');
        } finally {
            setStopping(false);
        }
    };

    if (!isRunning) return null;

    return (
        <Box sx={{ mb: 3 }}>
            <Alert
                severity="info"
                icon={false}
                sx={{ display: 'block' }}
                action={
                    <Button
                        color="error"
                        size="small"
                        variant="outlined"
                        onClick={handleStop}
                        loading={stopping}
                        disabled={stopRequested}
                    >
                        {stopRequested ? 'Stopping…' : 'Stop training'}
                    </Button>
                }
            >
                <Typography variant="body2" sx={{ mb: 1 }}>
                    {stopRequested
                        ? 'Stopping training. The run is finishing its current step; no model will be saved.'
                        : 'Training is in progress. This page will update automatically when complete.'}
                </Typography>
                <LinearProgress />
            </Alert>
        </Box>
    );
};
