"use client"

import React, { useState, useRef } from 'react';
import { Box, Button, Typography, Paper } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { uploadTrainingDoc, runManualTraining } from '@/services/trainingService';
import toast from 'react-hot-toast';

export default function TrainingUpload({ onUpload, unprocessedDocsCount }) {
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef(null);

    const handleFilesSelected = async (files) => {
        if (!files || files.length === 0) return;

        const docxFiles = Array.from(files).filter(file => file.name.endsWith('.docx'));

        if (docxFiles.length === 0) {
            toast.error("No .docx files selected. Only .docx files are supported.");
            return;
        }

        if (docxFiles.length < files.length) {
            toast.error("Some selected files were not .docx and have been ignored.", { duration: 4000 });
        }

        const toastId = toast.loading(`Uploading ${docxFiles.length} document(s)...`);
        const uploadPromises = docxFiles.map(file => uploadTrainingDoc(file));

        try {
            await Promise.all(uploadPromises);
            toast.success(`${docxFiles.length} document(s) uploaded successfully.`, { id: toastId });
            if (onUpload) onUpload();
        } catch (error) {
            toast.error(`An error occurred during upload: ${error.message}`, { id: toastId });
        }
    };

    const handleDragEvents = (e) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const handleDrop = (e) => {
        handleDragEvents(e);
        setIsDragging(false);
        if (e.dataTransfer.files) {
            handleFilesSelected(e.dataTransfer.files);
        }
    };

    const handleRunTraining = async () => {
        const toastId = toast.loading("Starting training process...");
        try {
            const response = await runManualTraining();
            toast.success(`Training started on ${response.documents} documents.`, { id: toastId });
        } catch (error) {
            toast.error(error.message, { id: toastId });
        }
    };

    return (
        <Paper sx={{ p: 3, mb: 4 }}>
            <Typography variant="h6" gutterBottom>Upload Training Document (.docx)</Typography>
            <Button
                fullWidth
                sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    p: 4,
                    mb: 2,
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
                onDragEnter={(e) => { handleDragEvents(e); setIsDragging(true); }}
                onDragOver={handleDragEvents}
                onDragLeave={(e) => { handleDragEvents(e); setIsDragging(false); }}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    hidden
                    accept=".docx"
                    onChange={(e) => handleFilesSelected(e.target.files)}
                />
                <Box sx={{ pointerEvents: 'none', textAlign: 'center' }}>
                    <CloudUploadIcon sx={{ fontSize: 48, color: 'grey.500', mb: 1 }} />
                    <Typography variant="h6">
                        Drag & drop .docx files here
                    </Typography>
                    <Typography color="text.secondary">
                        or click to select files
                    </Typography>
                </Box>
            </Button>

            <Button
                variant="contained"
                color="primary"
                onClick={handleRunTraining}
                disabled={unprocessedDocsCount === 0}
            >
                Run Training on {unprocessedDocsCount} Unprocessed Document(s)
            </Button>
        </Paper>
    );
}
