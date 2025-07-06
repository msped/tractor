"use client"

import React, { useState, useRef } from 'react';
import NextLink from 'next/link';
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
    DialogTitle,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Typography,
    IconButton,
    Stack,
    TextField,
    InputAdornment
} from '@mui/material';
import { useSession } from 'next-auth/react';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import ArticleIcon from '@mui/icons-material/Article';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import apiClient from '@/api/apiClient';

const getStatusChipColor = (status) => {
    switch (status) {
        case 'Processing':
            return 'primary';
        case 'Ready for Review':
            return 'warning';
        case 'Completed':
            return 'success';
        case 'Error':
            return 'error';
        default:
            return 'default';
    }
};

export default function CaseDocuments({ caseId, documents }) {
    const [docs, setDocs] = useState(documents || []);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef(null);
    const { data: session } = useSession();

    const handleOpenDialog = () => setDialogOpen(true);
    const handleCloseDialog = () => {
        setDialogOpen(false);
        setSelectedFiles([]);
        setIsDragging(false);
    };

    const handleFilesSelected = (files) => {
        if (files && files.length > 0) {
            const newFiles = Array.from(files).map(file => {
                const lastDot = file.name.lastIndexOf('.');
                const name = lastDot > 0 ? file.name.substring(0, lastDot) : file.name;
                const extension = lastDot > 0 ? file.name.substring(lastDot) : '';

                return { file, name, extension, id: `${file.name}-${file.lastModified}-${file.size}` };
            });

            setSelectedFiles(prevFiles => {
                const existingIds = new Set(prevFiles.map(f => f.id));
                const uniqueNewFiles = newFiles.filter(nf => !existingIds.has(nf.id));
                return [...prevFiles, ...uniqueNewFiles];
            });
        }
    };

    const handleDragEvents = (e) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const handleDragEnter = (e) => {
        handleDragEvents(e);
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        handleDragEvents(e);
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        handleDragEvents(e);
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFilesSelected(e.dataTransfer.files);
            e.dataTransfer.clearData();
        }
    };

    const handleFileNameChange = (id, newName) => {
        setSelectedFiles(prevFiles =>
            prevFiles.map(f => (f.id === id ? { ...f, name: newName } : f))
        );
    };

    const handleRemoveFile = (id) => {
        setSelectedFiles(prevFiles => prevFiles.filter(f => f.id !== id));
    };

    const handleDeleteDocument = async (docId) => {
        if (!caseId) return;

        try {
            await apiClient.delete(`/cases/documents/${docId}`, {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            });
            setDocs(prevDocs => prevDocs.filter(doc => doc.id !== docId));
        } catch (error) {
            console.error('Delete failed:', error);
            // TODO: Add user-facing error notification
        }
    };


    const handleUpload = async () => {
        if (selectedFiles.length === 0 || !caseId) return;

        const formData = new FormData();
        selectedFiles.forEach(selected => {
            const finalFilename = `${selected.name}${selected.extension}`;
            const fileToUpload = new File([selected.file], finalFilename, { type: selected.file.type });
            formData.append('original_file', fileToUpload);
        });

        try {
            const response = await apiClient.post(`/cases/${caseId}/documents`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                    'Authorization': `Bearer ${session.access_token}`,
                },
            });
            // The backend returns an array of all created documents in a single response
            setDocs((prevDocs) => [...prevDocs, ...response.data]);
        } catch (error) {
            console.error('Upload failed:', error);
            // TODO: Add user-facing error notification
        } finally {
            handleCloseDialog();
        }
    };

    return (
        <>
            <Card variant="outlined">
                <CardHeader
                    title="Documents"
                    slotProps={{ title: { fontWeight: 600 }}}
                    action={
                        <Button
                            variant="contained"
                            startIcon={<UploadFileIcon />}
                            onClick={handleOpenDialog}
                        >
                            Upload Document
                        </Button>
                    }
                />
                <CardContent>
                    {docs.length > 0 ? (
                        <List>
                            {docs.map((doc, i) => (
                                <ListItem
                                    key={i}
                                    secondaryAction={
                                        <Stack direction="row" spacing={1} alignItems="center">
                                            {doc.status === 'Ready for Review' && (
                                                <Button 
                                                    component={NextLink} 
                                                    href={`/cases/${caseId}/documents/${doc.id}/review`} 
                                                    variant="contained" 
                                                    size="small"
                                                >
                                                    Review
                                                </Button>
                                            )}
                                            {doc.status === 'Completed' && (
                                                <Button 
                                                    component={NextLink} 
                                                    href={`/documents/${doc.id}/view`} 
                                                    variant="contained" 
                                                    size="small"
                                                >
                                                    Open
                                                </Button>
                                            )}
                                            <IconButton aria-label="delete" onClick={() => handleDeleteDocument(doc.id)}>
                                                <DeleteIcon />
                                            </IconButton>
                                        </Stack>
                                    }
                                >
                                    <ListItemIcon><ArticleIcon /></ListItemIcon>
                                    <ListItemText
                                        primary={
                                            <Stack direction="row" spacing={2} alignItems="center">
                                                <Typography variant="body1">{doc.filename}</Typography>
                                                <Chip
                                                    label={doc.status}
                                                    color={getStatusChipColor(doc.status)}
                                                    size="small"
                                                />
                                            </Stack>
                                        }
                                        secondary={`Uploaded: ${new Date(doc.uploaded_at).toLocaleDateString('en-GB')}`}
                                    />
                                </ListItem>
                            ))}
                        </List>
                    ) : (
                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                            No documents have been uploaded for this case.
                        </Typography>
                    )}
                </CardContent>
            </Card>

            <Dialog open={dialogOpen} onClose={handleCloseDialog} fullWidth maxWidth="md">
                <DialogTitle>Upload New Document</DialogTitle>
                <DialogContent>
                    <Box
                        sx={{
                            border: `2px dashed ${isDragging ? 'primary.main' : 'grey.400'}`,
                            borderRadius: 2,
                            p: 4,
                            textAlign: 'center',
                            cursor: 'pointer',
                            backgroundColor: isDragging ? 'action.hover' : 'transparent',
                            transition: 'background-color 0.2s, border-color 0.2s',
                        }}
                        onDragEnter={handleDragEnter}
                        onDragOver={handleDragEvents}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            hidden
                            multiple
                            onChange={(e) => handleFilesSelected(e.target.files)}
                        />
                        <CloudUploadIcon sx={{ fontSize: 48, color: 'grey.500', mb: 2 }} />
                        <Typography variant="h6">
                            Drag & drop files here
                        </Typography>
                        <Typography color="text.secondary">
                            or click to select files
                        </Typography>
                    </Box>
                    {selectedFiles.length > 0 && (
                        <Box sx={{ mt: 3 }}>
                            <Typography variant="subtitle1" gutterBottom>Files to upload:</Typography>
                            <List>
                                {selectedFiles.map((selected) => (
                                    <ListItem
                                        key={selected.id}
                                        sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: { sm: 'center' }, gap: 2, mb: 1, p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
                                    >
                                        <ListItemText
                                            primary={selected.file.name}
                                            secondary={`${(selected.file.size / 1024 / 1024).toFixed(2)} MB`}
                                            sx={{ flexGrow: 1, m: 0, width: '275px' }}
                                        />
                                        <TextField
                                            label="Save as filename"
                                            value={selected.name}
                                            onChange={(e) => handleFileNameChange(selected.id, e.target.value)}
                                            variant="outlined"
                                            size="small"
                                            sx={{ width: { xs: '100%', sm: '60%' } }}
                                            slotProps={{
                                                input: {
                                                    endAdornment: <InputAdornment position="end">{selected.extension}</InputAdornment>,
                                                }
                                            }}
                                        />
                                        <IconButton aria-label="delete" onClick={() => handleRemoveFile(selected.id)}>
                                            <DeleteIcon />
                                        </IconButton>
                                    </ListItem>
                                ))}
                            </List>
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseDialog}>Cancel</Button>
                    <Button onClick={handleUpload} variant="contained" disabled={selectedFiles.length === 0}>
                        Upload
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}
