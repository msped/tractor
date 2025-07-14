"use client"

import React, { useState } from 'react';
import { Box, Typography, Container, Switch, FormControlLabel, Button } from '@mui/material';
import NextLink from 'next/link';
import DocumentViewer from './redaction/DocumentViewer';

export default function DocumentViewComponent({ document, redactions }) {
    const [showColorCoded, setShowColorCoded] = useState(false);

    const handleToggleChange = (event) => {
        setShowColorCoded(event.target.checked);
    };

    return (
        <Box sx={{ display: 'flex', height: 'calc(100vh - 64px)', flexDirection: 'column' }}>
            <Container maxWidth={false} sx={{ my: 4, display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, pb: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <Box>
                        <Button component={NextLink} href={`/cases/${document.case}`} variant="contained" color="primary">
                            Back to Case
                        </Button>
                    </Box>
                    <Box>
                        <Typography variant="h5" component="h1">{document?.filename}</Typography>
                    </Box>
                    <Box sx={{
                        display: 'flex',
                        alignItems: 'center',
                        backgroundColor: 'background.paper',
                        padding: 1,
                        borderRadius: 1,
                    }}>
                        <FormControlLabel
                            control={<Switch checked={showColorCoded} onChange={handleToggleChange} />}
                            label="Show Color-coded Redactions"
                            sx={{
                                color: 'text.primary',
                            }}
                        />
                    </Box>
                </Box>
                <DocumentViewer
                    text={document?.extracted_text}
                    redactions={redactions}
                    viewMode={showColorCoded ? 'color-coded' : 'final'}
                />
            </Container>
        </Box>
    );
}