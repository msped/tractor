"use client";

import React, { useEffect, useState } from 'react';
import useSWR from 'swr';
import {
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    Switch,
    Typography,
} from '@mui/material';
import { useSession } from "@/contexts/SessionContext";
import { getReviewWorkflowSettings, updateReviewWorkflowSettings } from '@/services/caseService';
import toast from 'react-hot-toast';

export const ReviewWorkflowSettingsCard = () => {
    const { session } = useSession();
    const { data, isLoading, error, mutate } = useSWR(
        session?.user?.id ? ['review-workflow-settings'] : null,
        () => getReviewWorkflowSettings()
    );

    const [autoAcceptEnabled, setAutoAcceptEnabled] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [configureOpen, setConfigureOpen] = useState(false);

    useEffect(() => {
        if (data) {
            setAutoAcceptEnabled(data.auto_accept_enabled ?? false);
        }
    }, [data]);

    const handleClose = () => {
        setConfigureOpen(false);
        if (data) {
            setAutoAcceptEnabled(data.auto_accept_enabled ?? false);
        }
    };

    const handleSave = async () => {
        setIsSubmitting(true);
        try {
            await updateReviewWorkflowSettings({ auto_accept_enabled: autoAcceptEnabled });
            await mutate();
            setConfigureOpen(false);
            toast.success('Review workflow settings updated.');
        } catch {
            toast.error('Failed to update review workflow settings.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <>
            <Card>
                <CardContent>
                    <Typography variant="h6" component="h2">
                        Review Workflow
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Controls whether NER redaction suggestions are automatically accepted on processing.
                        When enabled, reviewers verify and remove incorrect redactions rather than approving each one.
                    </Typography>
                    {isLoading && <CircularProgress size={20} />}
                    {error && (
                        <Typography variant="body2" color="error">
                            Failed to load review workflow settings.
                        </Typography>
                    )}
                    {!isLoading && data && (
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Typography variant="body2" color="text.secondary">Auto-accept mode:</Typography>
                                {data.auto_accept_enabled ? (
                                    <Chip label="Enabled" color="success" size="small" />
                                ) : (
                                    <Chip label="Disabled" color="default" size="small" />
                                )}
                            </Box>
                            <Button variant="outlined" size="small" onClick={() => setConfigureOpen(true)}>
                                Configure
                            </Button>
                        </Box>
                    )}
                </CardContent>
            </Card>

            <Dialog open={configureOpen} onClose={handleClose} maxWidth="sm" fullWidth>
                <DialogTitle>Review Workflow Settings</DialogTitle>
                <DialogContent>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        When auto-accept is enabled, all NER redaction suggestions are automatically
                        accepted when a document finishes processing. Reviewers scroll through the
                        document and reject any redactions that should not apply.
                        Auto-accepted redactions are not used for model training.
                    </Typography>
                    <FormControlLabel
                        control={
                            <Switch
                                checked={autoAcceptEnabled}
                                onChange={(e) => setAutoAcceptEnabled(e.target.checked)}
                                color="success"
                            />
                        }
                        label="Enable auto-accept mode"
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleClose} disabled={isSubmitting}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={handleSave}
                        loading={isSubmitting}
                    >
                        Save
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
};
