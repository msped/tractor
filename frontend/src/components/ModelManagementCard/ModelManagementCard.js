"use client";

import React, { useState } from 'react';
import useSWR from 'swr';
import {
    Typography,
    Button,
    Chip,
    CircularProgress,
    Alert,
    Box,
    Card,
    CardContent,
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
    IconButton,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSession } from 'next-auth/react';
import { getModels, setActiveModel, deleteModel } from '@/services/trainingService';
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import toast from 'react-hot-toast';

const formatScore = (score) => {
    if (score === null || score === undefined) return 'N/A';
    return `${(score * 100).toFixed(2)}%`;
};

export const ModelManagementCard = () => {
    const { data: session } = useSession();
    const { data: models, error, isLoading, mutate } = useSWR(
        // The key: if access_token is null, SWR will not fetch.
        session?.access_token ? ['models', session.access_token] : null,
        // The fetcher: receives the key as arguments.
        ([key, token]) => getModels(token)
    );
    const [isSubmitting, setIsSubmitting] = useState(null);
    const [confirmDeleteModel, setConfirmDeleteModel] = useState(null);

    const handleSetActive = async (modelId) => {
        setIsSubmitting(modelId);
        try {
            // Pass the access token to the service function
            await setActiveModel(modelId, session?.access_token);
            toast.success('Model activated successfully!');
            await mutate();
        } catch (e) {
            toast.error(e.message || 'Failed to activate model.');
        } finally {
            setIsSubmitting(null);
        }
    };

    const handleDeleteConfirm = async () => {
        const modelId = confirmDeleteModel.id;
        setConfirmDeleteModel(null);
        setIsSubmitting(modelId);
        try {
            await deleteModel(modelId, session?.access_token);
            toast.success('Model deleted successfully.');
            await mutate();
        } catch (e) {
            toast.error(e.message || 'Failed to delete model.');
        } finally {
            setIsSubmitting(null);
        }
    };

    return (
        <>
        <ConfirmationDialog
            open={!!confirmDeleteModel}
            onClose={() => setConfirmDeleteModel(null)}
            onConfirm={handleDeleteConfirm}
            title="Delete Model"
            description={`Are you sure you want to delete "${confirmDeleteModel?.name}"? This will also remove the model files from disk and cannot be undone.`}
            confirmLabel="Delete"
            confirmColor="error"
        />
        <Card>
            <CardContent>
                <Typography variant="h5" component="h2" gutterBottom>
                    Active Redaction Model
                </Typography>
                <Typography color="text.secondary" sx={{ mb: 3 }}>
                    Select the trained SpanCat model to use for OPERATIONAL entity detection. GLiNER handles THIRD_PARTY entities automatically.
                </Typography>
                {isLoading && <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}><CircularProgress /></Box>}
                {error && <Alert severity="error">{error.message}</Alert>}
                {models && (
                    models.length > 0 ? (
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Created</TableCell>
                                    <TableCell>Precision</TableCell>
                                    <TableCell>Recall</TableCell>
                                    <TableCell>F1 Score</TableCell>
                                    <TableCell></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {models.map((model) => (
                                    <TableRow key={model.id}>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <Typography variant="subtitle2" component="span">{model.name}</Typography>
                                                {model.is_active && <Chip label="Active" color="success" size="small" />}
                                            </Box>
                                        </TableCell>
                                        <TableCell>{new Date(model.created_at).toLocaleString('en-GB')}</TableCell>
                                        <TableCell>{formatScore(model.precision)}</TableCell>
                                        <TableCell>{formatScore(model.recall)}</TableCell>
                                        <TableCell>{formatScore(model.f1_score)}</TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', gap: 1 }}>
                                                <Button
                                                    variant="contained"
                                                    onClick={() => handleSetActive(model.id)}
                                                    disabled={model.is_active || isSubmitting !== null || !session?.access_token}
                                                    size="small"
                                                >
                                                    {isSubmitting === model.id ? <CircularProgress color="inherit" size={20} /> : 'Set Active'}
                                                </Button>
                                                <IconButton
                                                    aria-label="delete model"
                                                    color="error"
                                                    onClick={() => setConfirmDeleteModel(model)}
                                                    disabled={isSubmitting !== null || !session?.access_token}
                                                    size="small"
                                                >
                                                    <DeleteIcon />
                                                </IconButton>
                                            </Box>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    ) : (
                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>No trained models found.</Typography>
                    )
                )}
            </CardContent>
        </Card>
        </>
    );
}
