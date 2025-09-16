"use client"

import React, { useState } from 'react';
import {
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
    Chip,
    IconButton,
    Tooltip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle, Button
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { deleteTrainingDoc } from '@/services/trainingService';
import toast from 'react-hot-toast';

export default function TrainingDocList({ docs }) {
    const handleDelete = async (docId, docName) => {
        const toastId = toast.loading(`Deleting ${docName}...`);
        try {
            await deleteTrainingDoc(docId);
            toast.success("Document deleted successfully.", { id: toastId });
        } catch (error) {
            toast.error(error.message, { id: toastId });
        } finally {
            handleCloseConfirmDialog();
        }
    };

    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState(null);

    const handleOpenConfirmDialog = (docId, docName) => {
        setDeleteTarget({ id: docId, name: docName });
        setDialogOpen(true);
    };

    const handleCloseConfirmDialog = () => {
        setDialogOpen(false);
        setDeleteTarget(null);
    };

    const handleConfirmDelete = () => {
        if (deleteTarget) {
            handleDelete(deleteTarget.id, deleteTarget.name);
        }
    };

    return (
        <>
            <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Uploaded Training Documents</Typography>
            <TableContainer>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Filename</TableCell>
                            <TableCell>Uploaded By</TableCell>
                            <TableCell>Uploaded At</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {docs.map((doc) => (
                            <TableRow key={doc.id}>
                                <TableCell>{doc.name}</TableCell>
                                <TableCell>{doc.created_by_username}</TableCell>
                                <TableCell>{new Date(doc.created_at).toLocaleString()}</TableCell>
                                <TableCell>
                                    <Chip label={doc.processed ? "Processed" : "Unprocessed"} color={doc.processed ? "success" : "warning"} size="small" />
                                </TableCell>
                                <TableCell>
                                    <Tooltip title="Delete Document">
                                        <IconButton onClick={() => handleOpenConfirmDialog(doc.id, doc.name)} size="small">
                                            <DeleteIcon />
                                        </IconButton>
                                    </Tooltip>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
            </Paper>

            <Dialog
                open={dialogOpen}
                onClose={handleCloseConfirmDialog}
            >
                <DialogTitle>Confirm Deletion</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Are you sure you want to delete &quot;{deleteTarget?.name}&quot;? This action cannot be undone.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseConfirmDialog}>Cancel</Button>
                    <Button onClick={handleConfirmDelete} color="error" variant="contained" autoFocus>Delete</Button>
                </DialogActions>
            </Dialog>
        </>
    );
}