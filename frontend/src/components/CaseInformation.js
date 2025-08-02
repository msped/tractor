"use client"

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import {
    Box,
    Button,
    Card,
    CardContent,
    CardHeader,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    Grid, IconButton, TextField, Typography
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import apiClient from '@/api/apiClient';
import toast from 'react-hot-toast';

const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-GB');
};

const formatDateForInput = (dateString) => {
    if (!dateString) return '';
    // HTML input type="date" requires YYYY-MM-DD format
    return new Date(dateString).toISOString().split('T')[0];
};

const getStatusChipColor = (status) => {
    switch (status) {
        case 'OPEN':
        case 'IN_PROGRESS':
        case 'UNDER_REVIEW':
            return 'primary';
        case 'COMPLETED':
        case 'CLOSED':
            return 'success';
        case 'WITHDRAWN':
            return 'default';
        case 'ERROR':
            return 'error';
        default:
            return 'default';
    }
};

const InfoItem = ({ label, children, value }) => (
    <Grid size={{ xs: 12, sm: 6, md: 4 }}>
        <Typography variant="overline" color="text.secondary" component="div">
            {label}
        </Typography>
        <Typography variant="body1" component="div" sx={{ fontWeight: 500 }}>
            {children || value || 'N/A'}
        </Typography>
    </Grid>
);

export default function CaseInformation({ caseObject, onUpdate }) {
    const router = useRouter();
    const { data: session } = useSession();
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [confirmDeleteDialogOpen, setConfirmDeleteDialogOpen] = useState(false);
    const [editableCase, setEditableCase] = useState(null);

    const handleOpenEditDialog = () => {
        setEditableCase({
            ...caseObject,
            data_subject_dob: formatDateForInput(caseObject.data_subject_dob),
            retention_review_date: formatDateForInput(caseObject.retention_review_date),
        });
        setEditDialogOpen(true);
    };

    const handleCloseEditDialog = () => {
        setEditDialogOpen(false);
        setEditableCase(null);
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setEditableCase(prev => ({ ...prev, [name]: value }));
    };

    const handleUpdateCase = async () => {
        if (!editableCase || !session) return;

        try {
            await apiClient.put(`/cases/${caseObject.id}`, editableCase, {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            });
            handleCloseEditDialog();
            toast.success('Case updated.');
            if (onUpdate) onUpdate(); else router.refresh();
        } catch (error) {
            toast.error('Failed to update case. Please try again.');
        }
    };

    const handleDeleteCase = async () => {
        if (!caseObject || !session) return;

        try {
            await apiClient.delete(`/cases/${caseObject.id}`, {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            });
            router.push('/cases');
            toast.success('Case deleted.');
        } catch (error) {
            toast.error('Failed to delete case. Please try again.');
        }
    };


    if (!caseObject) {
        return <Typography>Loading case information...</Typography>;
    }

    return (
        <>
            <Card variant="outlined">
                <CardHeader
                    title="Case Details"
                    action={
                        <IconButton aria-label="settings" onClick={handleOpenEditDialog}>
                            <SettingsIcon />
                        </IconButton>
                    }
                    slotProps={{ title: { variant: 'h5', fontWeight: 600 }}}
                />
                <CardContent>
                    <Grid container spacing={3}>
                        <InfoItem label="Case Reference" value={caseObject.case_reference} />
                        <InfoItem label="Status">
                            <Chip label={caseObject.status} color={getStatusChipColor(caseObject.status)} size="small" />
                        </InfoItem>
                        <InfoItem label="Data Subject" value={caseObject.data_subject_name} />
                        <InfoItem label="Date of Birth" value={formatDate(caseObject.data_subject_dob)} />
                        <InfoItem label="Created At" value={formatDate(caseObject.created_at)} />
                        <InfoItem label="Retention Review" value={formatDate(caseObject.retention_review_date)} />
                    </Grid>
                </CardContent>
            </Card>

            {/* Edit Case Dialog */}
            <Dialog open={editDialogOpen} onClose={handleCloseEditDialog} fullWidth maxWidth="sm">
                <DialogTitle>Edit Case Details</DialogTitle>
                <DialogContent>
                    {editableCase && (
                        <Box component="form" noValidate autoComplete="off" sx={{ mt: 1 }}>
                            <TextField
                                margin="dense"
                                name="case_reference"
                                label="Case Reference"
                                type="text"
                                fullWidth
                                variant="outlined"
                                value={editableCase.case_reference}
                                onChange={handleInputChange}
                            />
                            <TextField
                                margin="dense"
                                name="data_subject_name"
                                label="Data Subject Name"
                                type="text"
                                fullWidth
                                variant="outlined"
                                value={editableCase.data_subject_name}
                                onChange={handleInputChange}
                            />
                            <TextField
                                margin="dense"
                                name="data_subject_dob"
                                label="Date of Birth"
                                type="date"
                                fullWidth
                                variant="outlined"
                                value={editableCase.data_subject_dob}
                                onChange={handleInputChange}
                                shrink="true"
                            />
                            <TextField
                                margin="dense"
                                name="retention_review_date"
                                label="Retention Review Date"
                                type="date"
                                fullWidth
                                variant="outlined"
                                value={editableCase.retention_review_date}
                                onChange={handleInputChange}
                                shrink="true"
                            />
                        </Box>
                    )}
                </DialogContent>
                <DialogActions sx={{ justifyContent: 'space-between', px: 3, pb: 2 }}>
                    <Button variant='contained' onClick={() => { setConfirmDeleteDialogOpen(true); handleCloseEditDialog(); }} color="error">
                        Delete Case
                    </Button>
                    <Box>
                        <Button onClick={handleCloseEditDialog}>Cancel</Button>
                        <Button onClick={handleUpdateCase} variant="contained">Save</Button>
                    </Box>
                </DialogActions>
            </Dialog>

            {/* Confirm Delete Dialog */}
            <Dialog open={confirmDeleteDialogOpen} onClose={() => setConfirmDeleteDialogOpen(false)}>
                <DialogTitle>Confirm Deletion</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Are you sure you want to delete this case? This action cannot be undone.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => {setConfirmDeleteDialogOpen(false); handleOpenEditDialog();}}>Cancel</Button>
                    <Button onClick={handleDeleteCase} color="error" variant="contained">
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}
