import React from 'react';
import { Box, Typography, List, ListItem, Card, CardContent, CardActions, Button, Chip } from '@mui/material';

const getRedactionTypeLabel = (type) => {
    switch (type) {
        case 'PII': return 'Third-Party PII';
        case 'OP_DATA': return 'Operational Data';
        case 'DS_INFO': return 'Data Subject Information';
        default: return 'Suggestion';
    }
};

export default function RedactionSidebar({ redactions, onAccept, onReject, onRemove, onSuggestionMouseEnter, onSuggestionMouseLeave }) {
    return (
        <Box sx={{ width: '40%', borderLeft: 1, borderColor: 'divider', height: 'calc(100vh - 64px)', overflowY: 'auto', bgcolor: 'background.default' }}>
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', position: 'sticky', top: 0, bgcolor: 'background.paper', zIndex: 1 }}>
                <Typography variant="h6" color='text.primary'>Redactions</Typography>
            </Box>
            {redactions.length > 0 ? (
                <List>
                    {redactions.map((redaction) => (
                        <ListItem key={redaction.id} onMouseEnter={() => onSuggestionMouseEnter(redaction.id)} onMouseLeave={onSuggestionMouseLeave}>
                            <Card variant="outlined" sx={{ width: '100%' }}>
                                <CardContent>
                                    <Typography variant="body2" sx={{ fontStyle: 'italic', mb: 2 }}>{`"${redaction.text}"`}</Typography>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <Chip label={getRedactionTypeLabel(redaction.redaction_type)} size="small" />
                                        <Typography variant="caption" color="text.secondary">Source: {redaction.is_suggestion ? 'AI' : 'User'}</Typography>
                                    </Box>
                                </CardContent>
                                {redaction.is_suggestion && !redaction.is_accepted && (
                                    <CardActions sx={{ justifyContent: 'flex-end' }}>
                                        <Button size="small" variant='contained' color="error" onClick={() => onReject(redaction)}>Reject</Button>
                                        <Button size="small" variant='contained' color="success" onClick={() => onAccept(redaction.id)}>Accept</Button>
                                    </CardActions>
                                )}
                                {redaction.is_accepted && (
                                    <CardActions sx={{ justifyContent: 'flex-end' }}>
                                        <Button size="small" color="error" variant='contained' onClick={() => onRemove(redaction.id)}>Remove</Button>
                                    </CardActions>
                                )}
                            </Card>
                        </ListItem>
                    ))}
                </List>
            ) : (
                <Typography sx={{ p: 2, color: 'text.secondary' }}>No redactions or suggestions yet.</Typography>
            )}
        </Box>
    );
}