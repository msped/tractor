"use client";

import React, { useEffect, useState } from 'react';
import useSWR from 'swr';
import {
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    FormControlLabel,
    Switch,
    TextField,
    Typography,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { getExportSettings, updateExportSettings } from '@/services/caseService';
import toast from 'react-hot-toast';

export const DocumentExportSettingsCard = () => {
    const { data: session } = useSession();
    const { data, isLoading, error } = useSWR(
        session?.access_token ? ['export-settings', session.access_token] : null,
        ([, token]) => getExportSettings(token)
    );

    const [headerText, setHeaderText] = useState('');
    const [footerText, setFooterText] = useState('');
    const [watermarkText, setWatermarkText] = useState('');
    const [watermarkIncludeCaseRef, setWatermarkIncludeCaseRef] = useState(false);
    const [pageNumbersEnabled, setPageNumbersEnabled] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (data) {
            setHeaderText(data.header_text ?? '');
            setFooterText(data.footer_text ?? '');
            setWatermarkText(data.watermark_text ?? '');
            setWatermarkIncludeCaseRef(data.watermark_include_case_ref ?? false);
            setPageNumbersEnabled(data.page_numbers_enabled ?? false);
        }
    }, [data]);

    const handleSave = async () => {
        setIsSubmitting(true);
        try {
            await updateExportSettings(
                {
                    header_text: headerText,
                    footer_text: footerText,
                    watermark_text: watermarkText,
                    watermark_include_case_ref: watermarkIncludeCaseRef,
                    page_numbers_enabled: pageNumbersEnabled,
                },
                session?.access_token
            );
            toast.success('Export settings saved.');
        } catch (e) {
            toast.error(e.message || 'Failed to save export settings.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Card>
            <CardContent>
                <Typography variant="h6" component="h2" sx={{ mb: 2 }}>
                    Document Export Settings
                </Typography>

                {isLoading && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}>
                        <CircularProgress />
                    </Box>
                )}
                {error && (
                    <Typography color="error" sx={{ mb: 2 }}>
                        Failed to load export settings.
                    </Typography>
                )}

                {!isLoading && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            label="Header text"
                            value={headerText}
                            onChange={(e) => setHeaderText(e.target.value)}
                            fullWidth
                            size="small"
                            slotProps={{ 'htmlInput': { 'aria-label': 'header text' } }}
                        />
                        <TextField
                            label="Footer text"
                            value={footerText}
                            onChange={(e) => setFooterText(e.target.value)}
                            fullWidth
                            size="small"
                            slotProps={{ 'htmlInput': { 'aria-label': 'footer text' } }}
                        />
                        <TextField
                            label="Watermark text"
                            value={watermarkText}
                            onChange={(e) => setWatermarkText(e.target.value)}
                            fullWidth
                            size="small"
                            slotProps={{ 'htmlInput': { 'aria-label': 'watermark text' } }}
                        />
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={watermarkIncludeCaseRef}
                                    onChange={(e) => setWatermarkIncludeCaseRef(e.target.checked)}
                                    disabled={!watermarkText}
                                    slotProps={{ input: { 'aria-label': 'include case reference in watermark' } }}
                                />
                            }
                            label="Include case reference in watermark"
                        />
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={pageNumbersEnabled}
                                    onChange={(e) => setPageNumbersEnabled(e.target.checked)}
                                    slotProps={{ input: { 'aria-label': 'show page numbers' } }}
                                />
                            }
                            label="Show page numbers"
                        />
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <Button
                                variant="contained"
                                onClick={handleSave}
                                disabled={isSubmitting}
                            >
                                {isSubmitting ? <CircularProgress size={20} color="inherit" /> : 'Save'}
                            </Button>
                        </Box>
                    </Box>
                )}
            </CardContent>
        </Card>
    );
};
