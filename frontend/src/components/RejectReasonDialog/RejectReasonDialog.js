import React, { useState, useEffect } from 'react';
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, DialogContentText } from '@mui/material';

export const RejectReasonDialog = ({ open, onClose, onSubmit, redaction }) => {
    const [reason, setReason] = useState('');

    useEffect(() => {
        if (!open) setReason('');
    }, [open]);

    const handleSubmit = () => {
        onSubmit(redaction.id, reason);
        onClose();
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle>Reason for Rejection</DialogTitle>
            <DialogContent>
                <DialogContentText sx={{ mb: 2 }}>
                    Please provide a reason for rejecting the suggestion: <br />
                    <em>{`"${redaction?.text}"`}</em>
                </DialogContentText>
                <TextField autoFocus margin="dense" label="Rejection Reason" type="text" fullWidth multiline rows={3} variant="outlined" value={reason} onChange={(e) => setReason(e.target.value)} />
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button onClick={handleSubmit} variant="contained" disabled={!reason.trim()}>Submit</Button>
            </DialogActions>
        </Dialog>
    );
}