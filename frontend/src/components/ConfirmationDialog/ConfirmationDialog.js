import React from 'react';
import {
    Button,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
} from '@mui/material';

export const ConfirmationDialog = ({
    open,
    onClose,
    onConfirm,
    title,
    description,
    confirmLabel = 'Confirm',
    confirmColor = 'primary',
    loading = false,
}) => (
    <Dialog open={open} onClose={loading ? undefined : onClose}>
        <DialogTitle>{title}</DialogTitle>
        <DialogContent>
            <DialogContentText>{description}</DialogContentText>
        </DialogContent>
        <DialogActions>
            <Button onClick={onClose} disabled={loading}>Cancel</Button>
            <Button
                onClick={onConfirm}
                color={confirmColor}
                variant="contained"
                disabled={loading}
                startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
            >
                {confirmLabel}
            </Button>
        </DialogActions>
    </Dialog>
);
