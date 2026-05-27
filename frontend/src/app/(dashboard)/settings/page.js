"use client";

import React from 'react';
import {
    CircularProgress,
    Container,
    Grid,
} from '@mui/material';
import { useSession } from "@/contexts/SessionContext";
import { ApiKeysCard } from '@/components/ApiKeysCard';
import { CustomRecognizersCard } from '@/components/CustomRecognizersCard';
import { DocumentExportSettingsCard } from '@/components/DocumentExportSettingsCard';
import { ExemptionTemplatesCard } from '@/components/ExemptionTemplatesCard';
import { LLMPromptSettingsCard } from '@/components/LLMPromptSettingsCard';

export default function SettingsPage() {
    const { session, isPending } = useSession();
    const isAdmin = session?.user?.is_admin === true;

    if (isPending) {
        return (
            <Container sx={{ display: 'flex', justifyContent: 'center', mt: 5 }}>
                <CircularProgress />
            </Container>
        );
    }

    return (
        <Container maxWidth="lg" sx={{ mt: 4 }}>
            <Grid container spacing={3} sx={{ mt: 2 }}>
                <Grid size={{xs: 12, md: 6}}>
                    <ExemptionTemplatesCard />
                </Grid>
                <Grid size={{xs: 12, md: 6}}>
                    <DocumentExportSettingsCard />
                </Grid>
                <Grid size={{xs: 12}}>
                    <CustomRecognizersCard />
                </Grid>
                {isAdmin && (
                    <Grid size={{xs: 12, md: 6}}>
                        <ApiKeysCard />
                    </Grid>
                )}
                {isAdmin && (
                    <Grid size={{xs: 12, md: 6}}>
                        <LLMPromptSettingsCard />
                    </Grid>
                )}
            </Grid>
        </Container>
    );
}
