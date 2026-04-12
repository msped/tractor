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
    TextField,
    Typography,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { getLLMPromptSettings, updateLLMPromptSettings } from '@/services/trainingService';
import toast from 'react-hot-toast';

export const LLMPromptSettingsCard = () => {
    const { data: session } = useSession();
    const { data, isLoading, error } = useSWR(
        session?.access_token ? ['llm-prompt-settings', session.access_token] : null,
        ([, token]) => getLLMPromptSettings(token)
    );

    const [systemPrompt, setSystemPrompt] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [configureOpen, setConfigureOpen] = useState(false);

    useEffect(() => {
        if (data) {
            setSystemPrompt(data.system_prompt ?? '');
        }
    }, [data]);

    const handleOpenConfigure = () => setConfigureOpen(true);

    const handleCloseConfigure = () => {
        setConfigureOpen(false);
        if (data) {
            setSystemPrompt(data.system_prompt ?? '');
        }
    };

    const handleResetToDefault = () => {
        if (data?.default_system_prompt) {
            setSystemPrompt(data.default_system_prompt);
        }
    };

    const handleSave = async () => {
        setIsSubmitting(true);
        try {
            await updateLLMPromptSettings(
                { system_prompt: systemPrompt },
                session?.access_token
            );
            toast.success('Prompt settings saved.');
            setConfigureOpen(false);
        } catch (e) {
            toast.error(e.message || 'Failed to update prompt settings.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <>
            <Dialog open={configureOpen} onClose={handleCloseConfigure} maxWidth="sm" fullWidth>
                <DialogTitle>Contextual AI Prompt Settings</DialogTitle>
                <DialogContent>
                    {isLoading && (
                        <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}>
                            <CircularProgress />
                        </Box>
                    )}
                    {error && (
                        <Typography color="error" sx={{ mb: 2 }}>
                            Failed to load prompt settings.
                        </Typography>
                    )}
                    {!isLoading && (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                            <TextField
                                label="System prompt"
                                value={systemPrompt}
                                onChange={(e) => setSystemPrompt(e.target.value)}
                                fullWidth
                                multiline
                                minRows={10}
                                slotProps={{ htmlInput: { 'aria-label': 'system prompt' } }}
                            />
                            <Button
                                variant="text"
                                size="small"
                                onClick={handleResetToDefault}
                                sx={{ alignSelf: 'flex-start' }}
                            >
                                Reset to default
                            </Button>
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
                        Contextual AI Prompt
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        The system prompt sent to the contextual AI model when analysing documents.
                        Edits take effect on the next document processed.
                    </Typography>
                    <Button variant="outlined" onClick={handleOpenConfigure}>
                        Configure
                    </Button>
                </CardContent>
            </Card>
        </>
    );
};
