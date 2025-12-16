"use client";

import React from 'react';
import {
    Container,
    Typography,
    Grid,
    Card,
    CardContent,
    Button
} from '@mui/material';
import { ModelManagementCard } from '@/components/ModelManagementCard';
import { TrainingSettingsCard } from '@/components/TrainingSettingsCard';

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
                <Grid size={{xs: 12, md: 5 }}>
                    <TrainingSettingsCard />
                </Grid>
                <Grid component={Card} size={{ xs: 12, md: 7 }}>
                    <CardContent>
                        <Typography variant="h5" component="h3">
                            How to provide manual training data
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            To provide manual training data, navigate to the Manual Training section 
                            where you can upload documents labelled documents.
                            This helps improve the models accuracy in detecting and redacting 
                            data.
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                            The only supported files for training are docx files. The document must
                            be highlighted using turquoise for operation data and bright green 
                            for Third Party information.
                        </Typography>
                    </CardContent>
                </Grid>
                <Grid size={{xs: 12}}>
                    <ModelManagementCard />
                </Grid>
            </Grid>
        </Container>
    );
}
