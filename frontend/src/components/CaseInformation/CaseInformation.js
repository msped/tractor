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
    Grid, IconButton, TextField, Typography,
    Menu, MenuItem, Tooltip
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { deleteCase, updateCase } from '@/services/caseService';
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

export const CaseInformation = ({ caseObject, onUpdate }) => {
    const router = useRouter();
    const { data: session } = useSession();
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [confirmDeleteDialogOpen, setConfirmDeleteDialogOpen] = useState(false);
    const [statusMenuAnchorEl, setStatusMenuAnchorEl] = useState(null);
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

    const handleStatusMenuOpen = (event) => {
        setStatusMenuAnchorEl(event.currentTarget);
    };

    const handleStatusMenuClose = () => {
        setStatusMenuAnchorEl(null);
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setEditableCase(prev => ({ ...prev, [name]: value }));
    };

    const handleUpdateCase = async () => {
        if (!editableCase || !session) return;

        try {
            await updateCase(caseObject.id, editableCase, session?.access_token);
            handleCloseEditDialog();
            toast.success('Case updated.');
            if (onUpdate) onUpdate(); else router.refresh();
        } catch (error) {
            toast.error('Failed to update case. Please try again.');
        }
    };

    const handleStatusChange = async (newStatus) => {
        handleStatusMenuClose();
        if (!caseObject || !session) return;

        const toastId = toast.loading(`Updating status...`);
        try {
            await updateCase(caseObject.id, { status: newStatus }, session?.access_token);
            toast.success('Case status updated.', { id: toastId });
            if (onUpdate) onUpdate();
        } catch (error) {
            toast.error('Failed to update case status.', { id: toastId });
        }
    };

    const handleDeleteCase = async () => {
        if (!caseObject || !session) return;

        try {
            await deleteCase(caseObject.id, session?.access_token);
            handleCloseEditDialog();
            router.push('/cases');
            toast.success('Case deleted.');
        } catch (error) {
            toast.error('Failed to delete case. Please try again.');
        }
    };


    if (!caseObject) {
        return <Typography>Loading case information...</Typography>;
    }

    const finalStatuses = ['COMPLETED', 'CLOSED', 'WITHDRAWN'];
    const isFinalStatus = finalStatuses.includes(caseObject.status);

    const availableStatuses = {
        'COMPLETED': 'Completed',
        'CLOSED': 'Closed',
        'WITHDRAWN': 'Withdrawn',
    };

    return (
        <>
            <Card variant="outlined">
                <CardHeader
                    title="Case Details"
                    action={
                        <>
                            <Tooltip title="Case Actions">
                                <span>
                                    <IconButton
                                        aria-label="case actions"
                                        onClick={handleStatusMenuOpen}
                                        disabled={isFinalStatus}
                                    >
                                        <MoreVertIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                            <Tooltip title={isFinalStatus ? "This case is finalised and cannot be edited." : "Edit Details"}>
                                <span>
                                    <IconButton
                                        aria-label="settings"
                                        onClick={handleOpenEditDialog}
                                        disabled={isFinalStatus}
                                    >
                                        <SettingsIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        </>
                    }
                    slotProps={{ title: { variant: 'h5', fontWeight: 600 }}}
                />
                <CardContent>
                    <Grid container spacing={3}>
                        <InfoItem label="Case Reference" value={caseObject.case_reference} />
                        <InfoItem label="Status">
                            <Chip label={caseObject.status_display} color={getStatusChipColor(caseObject.status)} size="small" />
                        </InfoItem>
                        <InfoItem label="Data Subject" value={caseObject.data_subject_name} />
                        <InfoItem label="Date of Birth" value={formatDate(caseObject.data_subject_dob)} />
                        <InfoItem label="Created At" value={formatDate(caseObject.created_at)} />
                        <InfoItem label="Retention Review" value={formatDate(caseObject.retention_review_date)} />
                    </Grid>
                </CardContent>
            </Card>

            <Menu
                anchorEl={statusMenuAnchorEl}
                open={Boolean(statusMenuAnchorEl)}
                onClose={handleStatusMenuClose}
            >
                {Object.entries(availableStatuses).map(([statusKey, statusLabel]) => (
                    <MenuItem
                        key={statusKey}
                        onClick={() => handleStatusChange(statusKey)}
                        disabled={caseObject.status === statusKey}
                    >
                        Mark as {statusLabel}
                    </MenuItem>
                ))}
            </Menu>

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
