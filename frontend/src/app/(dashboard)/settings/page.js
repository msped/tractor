"use client";

import React from 'react';
import {
    Container,
    Grid,
} from '@mui/material';
import { ModelManagementCard } from '@/components/ModelManagementCard';

export default function SettingsPage() {
    return (
        <Container maxWidth="lg" sx={{ mt: 4 }}>
            <Grid container spacing={3} sx={{ mt: 2 }}>
                <Grid size={{xs: 12}}>
                    <ModelManagementCard />
                </Grid>
            </Grid>
        </Container>
    );
}
