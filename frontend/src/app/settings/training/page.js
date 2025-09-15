"use client"

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Container, Typography, Grid, Card, CardContent, Box, Button } from "@mui/material";
import ScheduledTrainingCard from '@/components/ScheduledTrainingCard';
import TrainingRunList from '@/components/TrainingRunList';
import { getTrainingDocs, getTrainingSchedules, getTrainingRuns } from '@/services/trainingService';
import toast from 'react-hot-toast';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';

export default function TrainingPage() {
    const [docs, setDocs] = useState([]);
    const [schedule, setSchedule] = useState(null);
    const [runs, setRuns] = useState([]);

    const fetchDocs = useCallback(async () => {
        try {
            const [docsData, scheduleData, runsData] = await Promise.all([
                getTrainingDocs(),
                getTrainingSchedules(),
                getTrainingRuns()
            ]);
            setDocs(docsData);
            setSchedule(scheduleData);
            setRuns(runsData);
        } catch (error) {
            toast.error(error.message);
        }
    }, []);

    useEffect(() => {
        fetchDocs();
    }, [fetchDocs]);

    return (
        <>
            <Typography variant="h4" align='center' sx={{ mb: 4 }} fontWeight={600} gutterBottom>
                Model Training
            </Typography>
            <Grid container spacing={4}>
                <Grid component={Card} size={{xs: 12, md: 6}}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                <ModelTrainingIcon color="action" sx={{ mr: 1 }} />
                                <Typography variant="h6">Manual Training</Typography>
                            </Box>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                                Upload pre-highlighted .docx files to provide new examples for the model. The system will process these documents the next time a manual training run is started.
                            </Typography>
                            <Button 
                                href="/settings/training/manual"
                                variant="text" 
                                color="primary" 
                                component={Link} 
                                sx={{ mb: 2 }}>
                                Go to Manual Training
                            </Button>
                        </CardContent>
                </Grid>
                <Grid component={Card} size={{xs: 12, md: 6}}>
                    <ScheduledTrainingCard schedule={schedule} />
                </Grid>
            </Grid>

            <TrainingRunList runs={runs} />
        </>
    );
}
