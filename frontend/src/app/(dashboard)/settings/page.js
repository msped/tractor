"use client";

import React from 'react';
import {
    Container,
    Grid,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiKeysCard } from '@/components/ApiKeysCard';
import { DocumentExportSettingsCard } from '@/components/DocumentExportSettingsCard';
import { ExemptionTemplatesCard } from '@/components/ExemptionTemplatesCard';
import { ModelManagementCard } from '@/components/ModelManagementCard';

export default function SettingsPage() {
    const { data: session } = useSession();
    const isAdmin = session?.user?.is_staff === true;

    return (
        <Container maxWidth="lg" sx={{ mt: 4 }}>
            <Grid container spacing={3} sx={{ mt: 2 }}>
                <Grid size={{xs: 12, md: 6}}>
                    <ExemptionTemplatesCard />
                </Grid>
                <Grid size={{xs: 12, md: 6}}>
                    <DocumentExportSettingsCard />
                </Grid>
                {isAdmin && (
                    <Grid size={{xs: 12, md: 6}}>
                        <ApiKeysCard />
                    </Grid>
                )}
                <Grid size={{xs: 12}}>
                    <ModelManagementCard />
                </Grid>
            </Grid>
        </Container>
    );
}
