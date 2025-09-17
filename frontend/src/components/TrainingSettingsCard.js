"use client";

import React from 'react';
import { Card, CardContent, Typography, Button, Box } from '@mui/material';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import Link from 'next/link';

export default function TrainingSettingsCard() {
    return (
        <Card>
            <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <ModelTrainingIcon color="action" sx={{ mr: 1.5 }} />
                    <Typography variant="h5" component="h2">
                        Model Training
                    </Typography>
                </Box>
                <Typography color="text.secondary" sx={{ mb: 3 }}>
                    Manage manual and scheduled training runs to improve model performance over time.
                </Typography>
                <Button component={Link} href="/settings/training" variant="text">Go to Training</Button>
            </CardContent>
        </Card>
    );
}