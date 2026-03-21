"use client";

import React, { useEffect, useState } from 'react';
import useSWR from 'swr';
import {
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
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
    const [configureOpen, setConfigureOpen] = useState(false);

    useEffect(() => {
        if (data) {
            setHeaderText(data.header_text ?? '');
            setFooterText(data.footer_text ?? '');
            setWatermarkText(data.watermark_text ?? '');
            setWatermarkIncludeCaseRef(data.watermark_include_case_ref ?? false);
            setPageNumbersEnabled(data.page_numbers_enabled ?? false);
        }
    }, [data]);

    const handleOpenConfigure = () => setConfigureOpen(true);

    const handleCloseConfigure = () => {
        setConfigureOpen(false);
        if (data) {
            setHeaderText(data.header_text ?? '');
            setFooterText(data.footer_text ?? '');
            setWatermarkText(data.watermark_text ?? '');
            setWatermarkIncludeCaseRef(data.watermark_include_case_ref ?? false);
            setPageNumbersEnabled(data.page_numbers_enabled ?? false);
        }
    };

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
            setConfigureOpen(false);
        } catch (e) {
            toast.error(e.message || 'Failed to save export settings.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <>
            <Dialog open={configureOpen} onClose={handleCloseConfigure} maxWidth="sm" fullWidth>
                <DialogTitle>Document Export Settings</DialogTitle>
                <DialogContent>
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
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                            <TextField
                                label="Header text"
                                value={headerText}
                                onChange={(e) => setHeaderText(e.target.value)}
                                fullWidth
                                size="small"
                                multiline
                                minRows={2}
                                slotProps={{ 'htmlInput': { 'aria-label': 'header text' } }}
                            />
                            <TextField
                                label="Footer text"
                                value={footerText}
                                onChange={(e) => setFooterText(e.target.value)}
                                fullWidth
                                size="small"
                                multiline
                                minRows={2}
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
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseConfigure}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={handleSave}
                        disabled={isSubmitting}
                    >
                        {isSubmitting ? <CircularProgress size={20} color="inherit" /> : 'Save'}
                    </Button>
                </DialogActions>
            </Dialog>

            <Card>
                <CardContent>
                    <Typography variant="h6" component="h2">
                        Document Export Settings
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Applied to every exported PDF. Header and footer text appear in the page margins on each page.
                        The watermark is shown diagonally across the page and can optionally include the case reference.
                    </Typography>
                    <Button variant="outlined" onClick={handleOpenConfigure}>
                        Configure
                    </Button>
                </CardContent>
            </Card>
        </>
    );
};
