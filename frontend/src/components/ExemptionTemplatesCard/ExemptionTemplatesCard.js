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
    Divider,
    IconButton,
    TextField,
    Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSession } from 'next-auth/react';
import {
    createExemptionTemplate,
    deleteExemptionTemplate,
    getExemptionTemplates,
} from '@/services/redactionService';
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import toast from 'react-hot-toast';

export const ExemptionTemplatesCard = () => {
    const { data: session } = useSession();
    const { data: templates, error, isLoading, mutate } = useSWR(
        session?.access_token ? ['exemptions', session.access_token] : null,
        ([, token]) => getExemptionTemplates(token)
    );

    const [newName, setNewName] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [isAdding, setIsAdding] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(null);

    const handleAdd = async () => {
        if (!newName.trim()) return;
        setIsSubmitting(true);
        try {
            await createExemptionTemplate(
                { name: newName.trim(), description: newDescription.trim() },
                session?.access_token
            );
            toast.success('Exemption template added.');
            setNewName('');
            setNewDescription('');
            setIsAdding(false);
            await mutate();
        } catch (e) {
            toast.error(e.message || 'Failed to add template.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDeleteConfirm = async () => {
        const id = confirmDelete.id;
        setConfirmDelete(null);
        setIsSubmitting(true);
        try {
            await deleteExemptionTemplate(id, session?.access_token);
            toast.success('Exemption template deleted.');
            await mutate();
        } catch (e) {
            toast.error(e.message || 'Failed to delete template.');
        } finally {
            setIsSubmitting(false);
        }
    };

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
            <Card>
                <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                        <Box>
                            <Typography variant="h6" component="h2">
                                Exemption Templates
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Configurable rejection reasons shown to reviewers.
                            </Typography>
                        </Box>
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
                            sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', mb: 2 }}
                            onSubmit={(e) => { e.preventDefault(); handleAdd(); }}
                        >
                            <TextField
                                label="Name"
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                                size="small"
                                required
                                autoFocus
                                sx={{ flex: 2 }}
                                slotProps={{ 'htmlInput': { 'aria-label': 'template name' } }}
                            />
                            <TextField
                                label="Description (optional)"
                                value={newDescription}
                                onChange={(e) => setNewDescription(e.target.value)}
                                size="small"
                                sx={{ flex: 3 }}
                                slotProps={{ 'htmlInput': { 'aria-label': 'template description' } }}
                            />
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
                                ))}
                            </Box>
                        ) : (
                            <Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                                No exemption templates configured.
                            </Typography>
                        )
                    )}
                </CardContent>
            </Card>
        </>
    );
};
