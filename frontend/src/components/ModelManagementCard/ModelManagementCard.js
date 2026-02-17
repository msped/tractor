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
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { getModels, setActiveModel } from '@/services/trainingService';
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

    return (
        <Card>
            <CardContent>
                <Typography variant="h5" component="h2" gutterBottom>
                    Active Redaction Model
                </Typography>
                <Typography color="text.secondary" sx={{ mb: 3 }}>
                    Select the model to be used for suggesting redactions on new documents. Only one model can be active at a time.
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
                                            <Button
                                                variant="contained"
                                                onClick={() => handleSetActive(model.id)}
                                                disabled={model.is_active || isSubmitting !== null || !session?.access_token}
                                                size="small"
                                            >
                                                {isSubmitting === model.id ? <CircularProgress color="inherit" size={20} /> : 'Set Active'}
                                            </Button>
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
    );
}
