import React from 'react';
import { Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';

export const ResubmitDialog = ({ open, onClose, onConfirm, isConfirming }) => (
    <Dialog open={open} onClose={onClose}>
        <DialogTitle>Resubmit Document</DialogTitle>
        <DialogContent>
            <DialogContentText>
                This will delete all current redactions (including any manual redactions you have made) and reprocess the document with the current AI model. This action cannot be undone.
            </DialogContentText>
        </DialogContent>
        <DialogActions>
            <Button onClick={onClose} disabled={isConfirming}>
                Cancel
            </Button>
            <Button
                onClick={onConfirm}
                color="warning"
                variant="contained"
                disabled={isConfirming}
            >
                {isConfirming ? <CircularProgress size={24} color="inherit" /> : 'Resubmit'}
            </Button>
        </DialogActions>
    </Dialog>
);
