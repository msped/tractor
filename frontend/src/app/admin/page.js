"use client";

import React, { useState } from 'react';
import useSWR from 'swr';
import {
    Container,
    Typography,
    List,
    ListItem,
    ListItemText,
    Button,
    Chip,
    Paper,
    CircularProgress,
    Alert,
    Box,
    Divider
} from '@mui/material';
import { getModels, setActiveModel } from '@/services/trainingService';
import toast from 'react-hot-toast';

const modelsFetcher = () => getModels();

export default function ManageModelsPage() {
    const { data: models, error, isLoading, mutate } = useSWR('models', modelsFetcher);
    const [isSubmitting, setIsSubmitting] = useState(null);

    const handleSetActive = async (modelId) => {
        setIsSubmitting(modelId);
        try {
            await setActiveModel(modelId);
            toast.success('Model activated successfully!');
            await mutate();
        } catch (e) {
            toast.error(e.message || 'Failed to activate model.');
        } finally {
            setIsSubmitting(null);
        }
    };

    if (isLoading) {
        return (
            <Container maxWidth="md" sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
                <CircularProgress />
            </Container>
        );
    }

    if (error) {
        return (
            <Container maxWidth="md" sx={{ mt: 4 }}>
                <Alert severity="error">
                    {error.message}
                </Alert>
            </Container>
        );
    }

    return (
        <Container maxWidth="md" sx={{ mt: 4 }}>
            <Paper sx={{ p: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    Manage Redaction Models
                </Typography>
                <Typography color="text.secondary" sx={{ mb: 3 }}>
                    Activate a trained model to be used for suggesting redactions on new documents. Only one model can be active at a time.
                </Typography>
                <List>
                    {models && models.length > 0 ? models.map((model, index) => (
                        <React.Fragment key={model.id}>
                            <ListItem
                                secondaryAction={
                                    <Button variant="contained" onClick={() => handleSetActive(model.id)} disabled={model.is_active || isSubmitting !== null}>
                                        {isSubmitting === model.id ? <CircularProgress color="inherit" size={24} /> : 'Set as Active'}
                                    </Button>
                                }
                            >
                                <ListItemText
                                    primary={<Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}><Typography variant="h6" component="span">{model.name}</Typography>{model.is_active && (<Chip label="Active" color="success" size="small" />)}</Box>}
                                    secondary={
                                        <Box component="span" sx={{ display: 'flex', flexDirection: 'column', mt: 0.5 }}>
                                            <Typography component="span" variant="body2" color="text.secondary">
                                                Created: {new Date(model.created_at).toLocaleString('en-GB')}
                                            </Typography>
                                            {model.f1_score !== null ? (
                                                <Typography component="span" variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                                                    Precision: {model.precision?.toFixed(2) ?? 'N/A'} | Recall: {model.recall?.toFixed(2) ?? 'N/A'} | F1: {model.f1_score?.toFixed(2) ?? 'N/A'}
                                                </Typography>
                                            ) : (<Typography component="span" variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>No evaluation metrics available.</Typography>
                                            )}
                                        </Box>
                                    }
                                />
                            </ListItem>
                            {index < models.length - 1 && <Divider component="li" />}
                        </React.Fragment>
                    )) : (<Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>No trained models found. You can train a new model using the management command.</Typography>)}
                </List>
            </Paper>
        </Container>
    );
}

