"use client";

import React, { useState } from 'react';
import useSWR from 'swr';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    Dialog,
    DialogContent,
    DialogTitle,
    Divider,
    FormControlLabel,
    IconButton,
    Switch,
    TextField,
    Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import CloseIcon from '@mui/icons-material/Close';
import { useSession } from "@/contexts/SessionContext";
import {
    createExemptionTemplate,
    deleteExemptionTemplate,
    getExemptionTemplates,
    updateExemptionTemplate,
} from '@/services/redactionService';
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import toast from 'react-hot-toast';
import { toastError } from '@/api/toastError';

export const ExemptionTemplatesCard = () => {
    const { session } = useSession();
    const { data: templates, error, isLoading, mutate } = useSWR(
        session?.user?.id ? ['exemptions'] : null,
        () => getExemptionTemplates()
    );

    const [newName, setNewName] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [isAdding, setIsAdding] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(null);
    // A template redactions are withheld under can't be deleted; the server
    // says why, and the admin can deactivate it instead.
    const [inUse, setInUse] = useState(null);
    const [manageOpen, setManageOpen] = useState(false);

    const handleAdd = async () => {
        if (!newName.trim()) return;
        setIsSubmitting(true);
        try {
            await createExemptionTemplate(
                { name: newName.trim(), description: newDescription.trim() }
            );
            toast.success('Exemption template added.');
            setNewName('');
            setNewDescription('');
            setIsAdding(false);
            await mutate();
        } catch (e) {
            toastError(e, 'Failed to add template.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDeleteConfirm = async () => {
        const template = confirmDelete;
        setConfirmDelete(null);
        setIsSubmitting(true);
        try {
            await deleteExemptionTemplate(template.id);
            toast.success('Exemption template deleted.');
            await mutate();
        } catch (e) {
            if (e.status === 409) {
                setInUse({ template, message: e.message });
            } else {
                toastError(e, 'Failed to delete template.');
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDeactivateConfirm = async () => {
        const { template } = inUse;
        setInUse(null);
        setIsSubmitting(true);
        try {
            await updateExemptionTemplate(template.id, { is_active: false });
            toast.success('Exemption template deactivated.');
            await mutate();
        } catch (e) {
            toastError(e, 'Failed to deactivate template.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleTrainableChange = async (template, trainable) => {
        setIsSubmitting(true);
        try {
            await updateExemptionTemplate(template.id, { trainable });
            await mutate();
        } catch (e) {
            toastError(e, 'Failed to update template.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const templateCount = templates?.length ?? 0;

    return (
        <>
            <ConfirmationDialog
                open={!!confirmDelete}
                onClose={() => setConfirmDelete(null)}
                onConfirm={handleDeleteConfirm}
                title="Delete Exemption Template"
                description={`Are you sure you want to delete "${confirmDelete?.name}"? This cannot be undone.`}
                confirmLabel="Delete"
                confirmColor="error"
            />

            <ConfirmationDialog
                open={!!inUse}
                onClose={() => setInUse(null)}
                onConfirm={handleDeactivateConfirm}
                title="Template in use"
                description={inUse?.message}
                confirmLabel="Deactivate"
            />

            <Dialog open={manageOpen} onClose={() => setManageOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    Exemption Templates
                    <IconButton aria-label="close" onClick={() => setManageOpen(false)} size="small">
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
                        <Button
                            variant="contained"
                            startIcon={<AddIcon />}
                            onClick={() => setIsAdding(true)}
                            disabled={isAdding || isSubmitting}
                        >
                            Add
                        </Button>
                    </Box>

                    {isAdding && (
                        <Box
                            component="form"
                            sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2 }}
                            onSubmit={(e) => { e.preventDefault(); handleAdd(); }}
                        >
                            <TextField
                                label="Name"
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                                size="small"
                                required
                                autoFocus
                                fullWidth
                                slotProps={{ 'htmlInput': { 'aria-label': 'template name' } }}
                            />
                            <TextField
                                label="Description (optional)"
                                value={newDescription}
                                onChange={(e) => setNewDescription(e.target.value)}
                                size="small"
                                fullWidth
                                slotProps={{ 'htmlInput': { 'aria-label': 'template description' } }}
                            />
                            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                                <Button
                                    type="submit"
                                    variant="contained"
                                    disabled={!newName.trim() || isSubmitting}
                                >
                                    {isSubmitting ? <CircularProgress size={20} color="inherit" /> : 'Save'}
                                </Button>
                                <Button onClick={() => { setIsAdding(false); setNewName(''); setNewDescription(''); }}>
                                    Cancel
                                </Button>
                            </Box>
                        </Box>
                    )}

                    {isLoading && (
                        <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}>
                            <CircularProgress />
                        </Box>
                    )}
                    {error && <Alert severity="error">{error.message}</Alert>}
                    {templates && (
                        templates.length > 0 ? (
                            <Box>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Operational Data withheld under an exemption only teaches the model when that
                                    exemption trains it. Leave it off for exemptions that cover people&apos;s details.
                                </Typography>
                                {templates.map((template, index) => (
                                    <Box key={template.id}>
                                        {index > 0 && <Divider />}
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', py: 1 }}>
                                            <Box>
                                                <Typography variant="body2">{template.name}</Typography>
                                                {template.description && (
                                                    <Typography variant="caption" color="text.secondary">
                                                        {template.description}
                                                    </Typography>
                                                )}
                                            </Box>
                                            <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                                                <FormControlLabel
                                                    label="Trains model"
                                                    slotProps={{ typography: { variant: 'caption' } }}
                                                    control={
                                                        <Switch
                                                            size="small"
                                                            checked={template.trainable}
                                                            onChange={(e) => handleTrainableChange(template, e.target.checked)}
                                                            disabled={isSubmitting}
                                                            slotProps={{ input: { 'aria-label': `${template.name} trains the model` } }}
                                                        />
                                                    }
                                                />
                                                <IconButton
                                                    aria-label={`delete ${template.name}`}
                                                    color="error"
                                                    size="small"
                                                    onClick={() => setConfirmDelete(template)}
                                                    disabled={isSubmitting}
                                                >
                                                    <DeleteIcon />
                                                </IconButton>
                                            </Box>
                                        </Box>
                                    </Box>
                                ))}
                            </Box>
                        ) : (
                            <Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                                No exemption templates configured.
                            </Typography>
                        )
                    )}
                </DialogContent>
            </Dialog>

            <Card>
                <CardContent>
                    <Typography variant="h6" component="h2">
                        Exemption Templates
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Bases reviewers can withhold Operational Data under.
                    </Typography>
                    {templates && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {templateCount} {templateCount === 1 ? 'template' : 'templates'}
                        </Typography>
                    )}
                    <Button variant="outlined" onClick={() => setManageOpen(true)}>
                        Manage
                    </Button>
                </CardContent>
            </Card>
        </>
    );
};
