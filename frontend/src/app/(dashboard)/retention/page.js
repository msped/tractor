"use client";

import React, { useState } from 'react';
import useSWR from 'swr';
import {
    Alert,
    Box,
    CircularProgress,
    Container,
    Typography,
} from '@mui/material';
import { useSession } from "@/contexts/SessionContext";
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import { RetentionCaseTable } from '@/components/RetentionCaseTable';
import { getRetentionSettings, bulkDeleteCases } from '@/services/caseService';
import toast from 'react-hot-toast';

export default function RetentionPage() {
    const { session, isPending } = useSession();
    const isAdmin = session?.user?.is_admin === true;

    const { data, isLoading, error, mutate } = useSWR(
        isAdmin ? ['retention-settings'] : null,
        () => getRetentionSettings()
    );

    const [selectedIds, setSelectedIds] = useState(new Set());
    const [confirmState, setConfirmState] = useState(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const openConfirm = (ids) => setConfirmState({ ids });
    const closeConfirm = () => setConfirmState(null);

    const handleDelete = async () => {
        if (!confirmState) return;
        setIsDeleting(true);
        try {
            await bulkDeleteCases(confirmState.ids);
            const count = confirmState.ids.length;
            toast.success(`${count} case${count !== 1 ? 's' : ''} deleted.`);
            setSelectedIds(prev => {
                const next = new Set(prev);
                confirmState.ids.forEach(id => next.delete(id));
                return next;
            });
            mutate();
        } catch (e) {
            toast.error(e.message || 'Failed to delete cases.');
        } finally {
            setIsDeleting(false);
            closeConfirm();
        }
    };

    if (isPending) {
        return (
            <Container sx={{ display: 'flex', justifyContent: 'center', mt: 5 }}>
                <CircularProgress />
            </Container>
        );
    }

    if (!isAdmin) {
        return (
            <Container sx={{ mt: 4 }}>
                <Alert severity="error">You do not have permission to view this page.</Alert>
            </Container>
        );
    }

    return (
        <Container maxWidth="lg" sx={{ mt: 4 }}>
            <Typography variant="h5" component="h1" sx={{ mb: 1 }}>
                Retention Review
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Cases past their retention date or approaching it within{' '}
                {data?.retention_warning_days ?? 30} days.
                {data && !data.auto_case_deletion_enabled && (
                    <> Auto deletion is <strong>disabled</strong> — cases must be deleted manually.</>
                )}
            </Typography>

            {isLoading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 5 }}>
                    <CircularProgress />
                </Box>
            )}

            {error && (
                <Alert severity="error">Failed to load retention data.</Alert>
            )}

            {data && (
                <RetentionCaseTable
                    cases={[...data.past, ...data.upcoming].sort(
                        (a, b) => new Date(a.retention_review_date) - new Date(b.retention_review_date)
                    )}
                    selectedIds={selectedIds}
                    onSelectionChange={setSelectedIds}
                    onDeleteOne={(id) => openConfirm([id])}
                    onDeleteMany={(ids) => openConfirm(ids)}
                    isDeleting={isDeleting}
                />
            )}

            <ConfirmationDialog
                open={!!confirmState}
                onClose={closeConfirm}
                onConfirm={handleDelete}
                title="Delete cases"
                description={
                    confirmState?.ids.length === 1
                        ? 'Are you sure you want to permanently delete this case? This cannot be undone.'
                        : `Are you sure you want to permanently delete ${confirmState?.ids.length} cases? This cannot be undone.`
                }
                confirmLabel="Delete"
                confirmColor="error"
                loading={isDeleting}
            />
        </Container>
    );
}
