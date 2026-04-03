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
    IconButton,
    TextField,
    Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSession } from 'next-auth/react';
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import { getApiKeys, createApiKey, revokeApiKey } from '@/services/apiKeyService';
import toast from 'react-hot-toast';

export const ApiKeysCard = () => {
    const { data: session } = useSession();
    const { data: keys, error, isLoading, mutate } = useSWR(
        session?.access_token ? ['api-keys', session.access_token] : null,
        ([, token]) => getApiKeys(token)
    );

    const [description, setDescription] = useState('');
    const [isAdding, setIsAdding] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [newRawKey, setNewRawKey] = useState(null);
    const [confirmRevoke, setConfirmRevoke] = useState(null);
    const [manageOpen, setManageOpen] = useState(false);

    const handleCloseManage = () => {
        setManageOpen(false);
        setNewRawKey(null);
        setIsAdding(false);
        setDescription('');
    };

    const handleGenerate = async () => {
        if (!description.trim()) return;
        setIsSubmitting(true);
        try {
            const result = await createApiKey(description.trim(), session?.access_token);
            setNewRawKey(result.key);
            setDescription('');
            setIsAdding(false);
            await mutate();
        } catch (e) {
            toast.error(e.message || 'Failed to generate API key.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleRevokeConfirm = async () => {
        const id = confirmRevoke.id;
        setConfirmRevoke(null);
        setIsSubmitting(true);
        try {
            await revokeApiKey(id, session?.access_token);
            toast.success('API key revoked.');
            await mutate();
        } catch (e) {
            toast.error(e.message || 'Failed to revoke API key.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleCopy = () => {
        navigator.clipboard.writeText(newRawKey);
        toast.success('Key copied to clipboard.');
    };

    const keyCount = keys?.length ?? 0;

    return (
        <>
            <ConfirmationDialog
                open={!!confirmRevoke}
                onClose={() => setConfirmRevoke(null)}
                onConfirm={handleRevokeConfirm}
                title="Revoke API Key"
                description={`Are you sure you want to revoke "${confirmRevoke?.description}"? Any integrations using this key will stop working immediately.`}
                confirmLabel="Revoke"
                confirmColor="error"
            />

            <Dialog open={manageOpen} onClose={handleCloseManage} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    API Keys
                    <IconButton aria-label="close" onClick={handleCloseManage} size="small">
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent>
                    {newRawKey && (
                        <Alert
                            severity="warning"
                            sx={{ mb: 2 }}
                            action={
                                <Button
                                    startIcon={<ContentCopyIcon />}
                                    size="small"
                                    onClick={handleCopy}
                                    aria-label="copy key"
                                >
                                    Copy
                                </Button>
                            }
                        >
                            <Typography variant="body2" fontWeight="bold">
                                Copy this key now — it will not be shown again.
                            </Typography>
                            <Typography
                                variant="body2"
                                sx={{ fontFamily: 'monospace', wordBreak: 'break-all', mt: 0.5 }}
                                aria-label="generated api key"
                            >
                                {newRawKey}
                            </Typography>
                        </Alert>
                    )}

                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
                        <Button
                            variant="contained"
                            startIcon={<AddIcon />}
                            onClick={() => setIsAdding(true)}
                            disabled={isAdding || isSubmitting}
                        >
                            Generate Key
                        </Button>
                    </Box>

                    {isAdding && (
                        <Box
                            component="form"
                            sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2 }}
                            onSubmit={(e) => { e.preventDefault(); handleGenerate(); }}
                        >
                            <TextField
                                label="Description"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                size="small"
                                required
                                autoFocus
                                fullWidth
                                helperText="e.g. 'Case management integration'"
                                slotProps={{ htmlInput: { 'aria-label': 'key description' } }}
                            />
                            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                                <Button
                                    type="submit"
                                    variant="contained"
                                    disabled={!description.trim() || isSubmitting}
                                >
                                    {isSubmitting ? <CircularProgress size={20} color="inherit" /> : 'Generate'}
                                </Button>
                                <Button onClick={() => { setIsAdding(false); setDescription(''); }}>
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

                    {keys && (
                        keys.length > 0 ? (
                            <Box>
                                {keys.map((key, index) => (
                                    <Box key={key.id}>
                                        {index > 0 && <Divider />}
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', py: 1 }}>
                                            <Box>
                                                <Typography variant="body2">{key.description}</Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    Created {new Date(key.created_at).toLocaleDateString()}
                                                    {key.created_by_username && ` by ${key.created_by_username}`}
                                                </Typography>
                                            </Box>
                                            <IconButton
                                                aria-label={`revoke ${key.description}`}
                                                color="error"
                                                size="small"
                                                onClick={() => setConfirmRevoke(key)}
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
                                No API keys configured.
                            </Typography>
                        )
                    )}
                </DialogContent>
            </Dialog>

            <Card>
                <CardContent>
                    <Typography variant="h6" component="h2">
                        API Keys
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Allow external services to create cases via the REST API.
                    </Typography>
                    {keys && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {keyCount} active {keyCount === 1 ? 'key' : 'keys'}
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
