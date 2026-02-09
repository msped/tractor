"use client"

import React, { useState, useCallback } from 'react';
import { Box, Typography, Container, Switch, FormControlLabel, Button, Tooltip, IconButton } from '@mui/material';
import TextDecreaseIcon from '@mui/icons-material/TextDecrease';
import TextIncreaseIcon from '@mui/icons-material/TextIncrease';
import NextLink from 'next/link';
import { DocumentViewer } from '@/components/DocumentViewer';

const FONT_SIZE_STEPS = [0.75, 0.85, 1, 1.15, 1.3, 1.5];

export const DocumentViewComponent = ({ caseId, document, redactions }) => {
    const [showColorCoded, setShowColorCoded] = useState(false);
    const [fontSizeIndex, setFontSizeIndex] = useState(2);
    const baseFontSize = FONT_SIZE_STEPS[fontSizeIndex];
    const handleFontDecrease = useCallback(() => setFontSizeIndex(prev => Math.max(0, prev - 1)), []);
    const handleFontIncrease = useCallback(() => setFontSizeIndex(prev => Math.min(FONT_SIZE_STEPS.length - 1, prev + 1)), []);

    const handleToggleChange = (event) => {
        setShowColorCoded(event.target.checked);
    };

    return (
        <Box sx={{ display: 'flex', height: 'calc(100vh - 64px)', flexDirection: 'column' }}>
            <Container maxWidth={false} sx={{ my: 4, display: 'flex', flexDirection: 'column', flexGrow: 1, marginTop: 0 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, pb: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <Box>
                        <Button component={NextLink} href={`/cases/${caseId}`} variant="contained" color="primary">
                            Back to Case
                        </Button>
                    </Box>
                    <Box>
                        <Typography variant="h5" component="h1">{document?.filename}</Typography>
                    </Box>
                    <Box sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        padding: 1,
                        borderRadius: 1,
                    }}>
                        <Tooltip title="Decrease font size">
                            <span>
                                <IconButton
                                    aria-label="Decrease font size"
                                    onClick={handleFontDecrease}
                                    disabled={fontSizeIndex === 0}
                                    size="small"
                                    sx={{ fontSize: '0.85rem', fontWeight: 'bold' }}
                                >
                                    <TextDecreaseIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Increase font size">
                            <span>
                                <IconButton
                                    aria-label="Increase font size"
                                    onClick={handleFontIncrease}
                                    disabled={fontSizeIndex === FONT_SIZE_STEPS.length - 1}
                                    size="small"
                                    sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}
                                >
                                    <TextIncreaseIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
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
                    tables={document?.extracted_tables}
                    structure={document?.extracted_structure}
                    redactions={redactions}
                    viewMode={showColorCoded ? 'color-coded' : 'final'}
                    baseFontSize={baseFontSize}
                />
            </Container>
        </Box>
    );
}