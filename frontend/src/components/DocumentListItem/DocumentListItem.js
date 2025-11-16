import React, { useEffect } from 'react';
import {
    ListItem, 
    ListItemIcon, 
    ListItemText, 
    IconButton, 
    Button, 
    Stack, 
    Typography, 
    Chip,
    Tooltip,
    CircularProgress 
} from '@mui/material';
import ArticleIcon from '@mui/icons-material/Article';
import DeleteIcon from '@mui/icons-material/Delete';
import NextLink from 'next/link';

import { getDocument } from '@/services/documentService';

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


export const DocumentListItem = ({ 
    doc,
    caseId,
    onDelete,
    handleDocumentUpdate,
    isCaseFinalised 
}) => {

    // This useEffect handles polling for a newly uploaded document.
    // Once the status is no longer 'Processing', it calls the parent's update function
    // and stops its own polling.
    useEffect(() => {
        if (doc.status !== 'Processing') {
            return;
        }

        const intervalId = setInterval(async () => {
            try {
                const updatedDoc = await getDocument(doc.id);
                if (updatedDoc.status !== 'Processing') {
                    clearInterval(intervalId);
                    handleDocumentUpdate();
                }
            } catch (error) {
                console.error('Failed to poll document status:', error);
                clearInterval(intervalId);
            }
        }, 5000);

        return () => clearInterval(intervalId);

    }, [doc.id, doc.status, handleDocumentUpdate]);

    return (
        <ListItem
            secondaryAction={
                <Stack direction="row" spacing={1} alignItems="center">
                    {doc.status === 'Ready for Review' && (
                        <Button 
                            component={NextLink} 
                            href={`/cases/${caseId}/document/${doc.id}/review`} 
                            variant="contained" 
                            size="small"
                        >
                            Review
                        </Button>
                    )}
                    {doc.status === 'Completed' && (
                        <Button 
                            component={NextLink} 
                            href={`/cases/${caseId}/document/${doc.id}/view`} 
                            variant="contained" 
                            size="small"
                        >
                            Open
                        </Button>
                    )}
                    <Tooltip title={isCaseFinalised ? "Cannot delete documents from a finalised case." : "Delete document"}>
                        <span>
                            <IconButton aria-label="delete" onClick={() => onDelete(doc.id)} disabled={isCaseFinalised}>
                                <DeleteIcon />
                            </IconButton>
                        </span>
                    </Tooltip>
                </Stack>
            }
        >
            <ListItemIcon><ArticleIcon /></ListItemIcon>
            <ListItemText
                primary={
                    <Stack direction="row" spacing={2} alignItems="center">
                        <Typography variant="body1">{doc.filename}</Typography>
                        <Chip
                            icon={doc.status === 'Processing' && (
                                <CircularProgress size={10} />
                            )}
                            label={doc.status}
                            color={getStatusChipColor(doc.status)}
                            size="small"
                        />
                    </Stack>
                }
                secondary={`Uploaded: ${new Date(doc.uploaded_at).toLocaleDateString('en-GB')}`}
            />
        </ListItem>
    )
}
