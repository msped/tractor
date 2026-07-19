import React from 'react';
import {
    Button,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    List,
    ListItem,
    ListItemText,
} from '@mui/material';

/**
 * Confirms case-wide DS_INFO propagation during an Internal Review.
 *
 * The reviewer previews which other documents would gain redactions for the
 * marked term and confirms before anything is written. When no other document
 * is affected the dialog is not shown at all (handled by the caller).
 */
export const PropagationConfirmDialog = ({ open, preview, onCancel, onConfirm, loading = false }) => {
    const term = preview?.term ?? '';
    const affected = preview?.affected_documents ?? [];
    const totalMatches = preview?.total_matches ?? 0;

    return (
        <Dialog open={open} onClose={loading ? undefined : onCancel} fullWidth maxWidth="sm">
            <DialogTitle>Propagate data subject information?</DialogTitle>
            <DialogContent>
                <DialogContentText sx={{ mb: 2 }}>
                    Marking <em>{`"${term}"`}</em> as data subject information will redact{' '}
                    {totalMatches} further {totalMatches === 1 ? 'occurrence' : 'occurrences'} across{' '}
                    {affected.length} other {affected.length === 1 ? 'document' : 'documents'} in this case.
                </DialogContentText>
                <List dense disablePadding>
                    {affected.map((doc) => (
                        <ListItem key={doc.document_id} disableGutters>
                            <ListItemText
                                primary={doc.filename}
                                secondary={`${doc.match_count} ${doc.match_count === 1 ? 'match' : 'matches'}`}
                            />
                        </ListItem>
                    ))}
                </List>
            </DialogContent>
            <DialogActions>
                <Button onClick={onCancel} disabled={loading}>Cancel</Button>
                <Button
                    onClick={onConfirm}
                    variant="contained"
                    color="primary"
                    disabled={loading}
                    startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
                >
                    Propagate
                </Button>
            </DialogActions>
        </Dialog>
    );
};
