"use client";

import React from 'react';
import useSWR from 'swr';
import {
    Box,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Typography,
} from '@mui/material';
import { useSession } from "@/contexts/SessionContext";
import { getRetentionSettings } from '@/services/caseService';

export const RetentionSettingsCard = () => {
    const { session } = useSession();
    const { data, isLoading, error } = useSWR(
        session?.user?.id ? ['retention-settings'] : null,
        () => getRetentionSettings()
    );

    return (
        <Card>
            <CardContent>
                <Typography variant="h6" component="h2">
                    Auto Case Deletion
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Controls whether cases past their retention date are automatically deleted daily.
                    Configure via the <code>AUTO_CASE_DELETION_ENABLED</code> environment variable.
                </Typography>
                {isLoading && <CircularProgress size={20} />}
                {error && (
                    <Typography variant="body2" color="error">
                        Failed to load retention settings.
                    </Typography>
                )}
                {!isLoading && data && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" color="text.secondary">Status:</Typography>
                        {data.auto_case_deletion_enabled ? (
                            <Chip label="Enabled" color="success" size="small" />
                        ) : (
                            <Chip label="Disabled" color="default" size="small" />
                        )}
                    </Box>
                )}
            </CardContent>
        </Card>
    );
};
