"use client"

import React, { useState, useRef } from 'react';
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
    Tab,
    Tabs,
    Typography,
    IconButton,
    TextField,
    InputAdornment,
    Tooltip
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';

import { uploadDocuments, deleteDocument, resubmitDocument, cancelProcessing } from '@/services/documentService';
import { DocumentListItem } from '@/components/DocumentListItem';
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import toast from 'react-hot-toast';


export const CaseDocuments = ({ caseId, documents, onUpdate, isCaseFinalised }) => {
    const [dialogOpen, setDialogOpen] = useState(false);
    const [activeTab, setActiveTab] = useState(0);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [isDragging, setIsDragging] = useState(false);
    const [pasteName, setPasteName] = useState('');
    const [pasteText, setPasteText] = useState('');
    const [pendingDeleteDoc, setPendingDeleteDoc] = useState(null);
    const [isDeletingDoc, setIsDeletingDoc] = useState(false);
    const fileInputRef = useRef(null);

    const handleOpenDialog = () => setDialogOpen(true);
    const handleCloseDialog = () => {
        setDialogOpen(false);
        setActiveTab(0);
        setSelectedFiles([]);
        setIsDragging(false);
        setPasteName('');
        setPasteText('');
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

    const handleDeleteDocument = async () => {
        if (!caseId || !pendingDeleteDoc) return;
        const docId = pendingDeleteDoc.id;
        setIsDeletingDoc(true);

        try {
            await deleteDocument(docId);
            setPendingDeleteDoc(null);
            toast.success('Document deleted.');
            if (onUpdate) await onUpdate();
        } catch (error) {
            toast.error('Failed to delete document. Please try again.');
        } finally {
            setIsDeletingDoc(false);
        }
    };

    const handleResubmitDocument = async (docId) => {
        if (!caseId) return;

        try {
            await resubmitDocument(docId);
            toast.success('Document resubmitted for processing.');
            if (onUpdate) await onUpdate();
        } catch (error) {
            toast.error('Failed to resubmit document. Please try again.');
        }
    };

    const handleCancelProcessing = async (docId) => {
        if (!caseId) return;

        try {
            await cancelProcessing(docId);
            toast.success('Document processing cancelled.');
            if (onUpdate) await onUpdate();
        } catch (error) {
            toast.error('Failed to cancel processing. Please try again.');
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
            await uploadDocuments(caseId, formData);
            handleCloseDialog();
            toast.success('Documents uploaded successfully.');
            if (onUpdate) await onUpdate();
        } catch (error) {
            toast.error(error.message || 'Failed to upload documents. Please try again.');
        }
    };

    const handlePasteSubmit = async () => {
        if (!pasteName.trim() || !pasteText.trim() || !caseId) return;

        const file = new File([pasteText], `${pasteName.trim()}.txt`, { type: 'text/plain' });
        const formData = new FormData();
        formData.append('original_file', file);

        try {
            await uploadDocuments(caseId, formData);
            handleCloseDialog();
            toast.success('Document created successfully.');
            if (onUpdate) await onUpdate();
        } catch (error) {
            toast.error(error.message || 'Failed to create document. Please try again.');
        }
    };

    return (
        <>
            <ConfirmationDialog
                open={!!pendingDeleteDoc}
                onClose={() => setPendingDeleteDoc(null)}
                onConfirm={handleDeleteDocument}
                title="Delete Document"
                description={`Are you sure you want to delete "${pendingDeleteDoc?.filename}"? This cannot be undone.`}
                confirmLabel="Delete"
                confirmColor="error"
                loading={isDeletingDoc}
            />
            <Card variant="outlined">
                <CardHeader
                    title="Documents"
                    slotProps={{ title: { fontWeight: 600 }}}
                    action={
                        <Tooltip title={isCaseFinalised ? "This case is finalised and no longer accepts new documents." : ""}>
                            <span>
                                <Button
                                    variant="contained"
                                    startIcon={<AddIcon />}
                                    onClick={handleOpenDialog}
                                    disabled={isCaseFinalised}
                                >
                                    Add Document
                                </Button>
                            </span>
                        </Tooltip>
                    }
                />
                <CardContent>
                    {documents && documents.length > 0 ? (
                        <List>
                            {documents.map((doc) => (
                                <DocumentListItem
                                    key={doc.id}
                                    doc={doc}
                                    caseId={caseId}
                                    onDelete={(docId) => setPendingDeleteDoc(documents.find(d => d.id === docId))}
                                    onResubmit={handleResubmitDocument}
                                    onCancelProcessing={handleCancelProcessing}
                                    handleDocumentUpdate={onUpdate}
                                    isCaseFinalised={isCaseFinalised}
                                />
                            ))}
                        </List>
                    ) : (
                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                            No documents have been added for this case.
                        </Typography>
                    )}
                </CardContent>
            </Card>

            <Dialog open={dialogOpen} onClose={handleCloseDialog} fullWidth maxWidth="md">
                <DialogTitle>Add Document</DialogTitle>
                <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }}>
                    <Tab label="Upload File" />
                    <Tab label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            Paste Text
                            <Chip label="Alpha" size="small" color="warning" variant="outlined" />
                        </Box>
                    } />
                </Tabs>
                <DialogContent>
                    {activeTab === 0 && (
                        <>
                            <input
                                ref={fileInputRef}
                                id="file-upload-input"
                                type="file"
                                hidden
                                multiple
                                onChange={(e) => {
                                    handleFilesSelected(e.target.files)
                                    e.target.value = null;
                                }}
                            />
                            <Button
                                fullWidth
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    p: 4,
                                    textTransform: 'none',
                                    color: 'text.primary',
                                    fontWeight: 'normal',
                                    border: `2px dashed ${isDragging ? 'primary.main' : 'grey.400'}`,
                                    borderRadius: 2,
                                    backgroundColor: isDragging ? 'action.hover' : 'transparent',
                                    transition: 'background-color 0.2s, border-color 0.2s',
                                    '&:hover': {
                                        backgroundColor: 'action.hover',
                                    },
                                }}
                                onDragEnter={handleDragEnter}
                                onDragOver={handleDragEvents}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                            >
                                <Box sx={{ pointerEvents: 'none', textAlign: 'center' }}>
                                    <CloudUploadIcon sx={{ fontSize: 48, color: 'grey.500', mb: 2 }} />
                                    <Typography variant="h6">
                                        Drag & drop files here
                                    </Typography>
                                    <Typography color="text.secondary">
                                        or click to select files
                                    </Typography>
                                </Box>
                            </Button>
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
                        </>
                    )}
                    {activeTab === 1 && (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                            <TextField
                                label="Document name"
                                value={pasteName}
                                onChange={(e) => setPasteName(e.target.value)}
                                required
                                fullWidth
                                size="small"
                                slotProps={{
                                    input: {
                                        endAdornment: <InputAdornment position="end">.txt</InputAdornment>,
                                    }
                                }}
                            />
                            <TextField
                                label="Paste document text"
                                value={pasteText}
                                onChange={(e) => setPasteText(e.target.value)}
                                required
                                fullWidth
                                multiline
                                rows={20}
                                placeholder="Paste the document content here..."
                                helperText="Plain text only — table formatting will not be preserved."
                            />
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseDialog}>Cancel</Button>
                    {activeTab === 0 && (
                        <Button onClick={handleUpload} variant="contained" disabled={selectedFiles.length === 0}>
                            Upload
                        </Button>
                    )}
                    {activeTab === 1 && (
                        <Button
                            onClick={handlePasteSubmit}
                            variant="contained"
                            disabled={!pasteName.trim() || !pasteText.trim()}
                        >
                            Create
                        </Button>
                    )}
                </DialogActions>
            </Dialog>
        </>
    );
}
