"use client";

import React from 'react';
import {
    Container,
    Typography,
    Grid
} from '@mui/material';
import ModelManagementCard from '@/components/ModelManagementCard';
import TrainingSettingsCard from '@/components/TrainingSettingsCard';

export default function SettingsPage() {
    return (
        <Container maxWidth="lg" sx={{ mt: 4 }}>
            <Typography 
                variant="h4" 
                align='center' 
                fontWeight={600} 
                component="h1" 
                gutterBottom
            >
                Settings
            </Typography>
            <Grid container spacing={3} sx={{ mt: 2 }}>
                <Grid  size={{xs: 12, md: 6}}>
                    <TrainingSettingsCard />
                </Grid>
                <Grid item size={{xs: 12}}>
                    <ModelManagementCard />
                </Grid>
            </Grid>
        </Container>
    );
}
