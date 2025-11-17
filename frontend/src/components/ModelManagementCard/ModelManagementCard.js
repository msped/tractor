"use client";

import React, { useState } from 'react';
import useSWR from 'swr';
import {
    Typography,
    List,
    ListItem,
    ListItemText,
    Button,
    Chip,
    CircularProgress,
    Alert,
    Box,
    Divider,
    Card,
    CardContent,
} from '@mui/material';
import { getModels, setActiveModel } from '@/services/trainingService';
import toast from 'react-hot-toast';

const modelsFetcher = () => getModels();

export const ModelManagementCard = () => {
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
                    <List disablePadding>
                        {models.length > 0 ? models.map((model, index) => (
                            <React.Fragment key={model.id}>
                                <ListItem
                                    disablePadding
                                    secondaryAction={
                                        <Box sx={{ display: 'flex', gap: 1 }}>
                                            <Button variant="contained" onClick={() => handleSetActive(model.id)} disabled={model.is_active || isSubmitting !== null} size="small">
                                                {isSubmitting === model.id ? <CircularProgress color="inherit" size={20} /> : 'Set Active'}
                                            </Button>
                                        </Box>
                                    }
                                >
                                    <ListItemText
                                        primary={<Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}><Typography variant="subtitle1" component="span">{model.name}</Typography>{model.is_active && (<Chip label="Active" color="success" size="small" />)}</Box>}
                                        secondary={`Created: ${new Date(model.created_at).toLocaleString('en-GB')}`}
                                    />
                                </ListItem>
                                {index < models.length - 1 && <Divider component="li" sx={{ my: 2 }} />}
                            </React.Fragment>
                        )) : (<Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>No trained models found.</Typography>)}
                    </List>
                )}
            </CardContent>
        </Card>
    );
}