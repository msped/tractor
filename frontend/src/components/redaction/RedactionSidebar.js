import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, Accordion, AccordionSummary, AccordionDetails, List, ListItem, Card, CardContent, CardActions, Button, Chip } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const getRedactionTypeLabel = (type) => {
    switch (type) {
        case 'PII': return 'Third-Party PII';
        case 'OP_DATA': return 'Operational Data';
        case 'DS_INFO': return 'Data Subject Information';
        default: return 'Suggestion';
    }
};

export default function RedactionSidebar({ redactions, onAccept, onReject, onRemove, onSuggestionMouseEnter, onSuggestionMouseLeave, scrollToId, removeScrollId }) {
    const { rejected, accepted, pending, manual } = redactions;
    const redactionSections = Object.keys(redactions);
    const [expanded, setExpanded] = useState(new Set(['pending']));
    const itemRefs = useRef({});

    const handleAccordionChange = (panel) => (event, isExpanded) => {
        setExpanded(prev => {
            const newSet = new Set(prev);
            if (isExpanded) {
                newSet.add(panel);
            } else {
                newSet.delete(panel);
            }
            return newSet;
        });
    };

    useEffect(() => {
        if (!scrollToId) return;

        const targetSection = redactionSections.find(key =>
            redactions[key].some(item => item.id === scrollToId)
        );

        if (targetSection) {
            if (!expanded.has(targetSection)) {
                setExpanded(prev => new Set(prev).add(targetSection));
            }

            const timer = setTimeout(() => {
                const element = itemRefs.current[scrollToId];
                if (element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    element.style.backgroundColor = 'rgba(255, 214, 10, 0.4)';
                    setTimeout(() => {
                        element.style.backgroundColor = '';
                        removeScrollId();
                    }, 2000);
                }
            }, 150);

            return () => clearTimeout(timer);
        }
    }, [scrollToId, redactions, redactionSections, expanded, removeScrollId]);

    return (
        <Box sx={{ width: '40%', borderLeft: 1, borderColor: 'divider', height: 'calc(100vh - 64px)', overflowY: 'auto', bgcolor: 'background.default' }}>
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', position: 'sticky', top: 0, bgcolor: 'background.paper', zIndex: 1 }}>
                <Typography variant="h6" color='text.primary'>Redactions</Typography>
            </Box>
            {(pending?.length > 0 || manual?.length > 0 || accepted?.length > 0 || rejected?.length > 0) ? (
                <Box sx={{ py: 2 }}>
                    {redactionSections.map((sectionKey) => {
                        const items = redactions[sectionKey];
                        if (items.length === 0) return null;

                        return (
                            <Accordion
                                key={sectionKey}
                                expanded={expanded.has(sectionKey)}
                                onChange={handleAccordionChange(sectionKey)}
                                disableGutters
                                sx={{ '&:not(:last-child)': { mb: 1 } }}
                            >
                                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                    <Typography sx={{ textTransform: 'capitalize' }}>{`${sectionKey} (${items.length})`}</Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <List dense sx={{ p: 0 }}>
                                        {items.map(item => (
                                            <ListItem key={item.id} ref={el => (itemRefs.current[item.id] = el)} sx={{ px: 0, '&:not(:last-child)': { mb: 1 } }} onMouseEnter={() => onSuggestionMouseEnter(item.id)} onMouseLeave={onSuggestionMouseLeave}>
                                                <Card variant="outlined" sx={{ width: '100%' }}>
                                                    <CardContent>
                                                        <Typography variant="body2" sx={{ fontStyle: 'italic', mb: 2 }}>{`"${item.text}"`}</Typography>
                                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                            <Chip label={getRedactionTypeLabel(item.redaction_type)} size="small" />
                                                            <Typography variant="caption" color="text.secondary">Source: {item.is_suggestion ? 'AI' : 'User'}</Typography>
                                                        </Box>
                                                        {item.justification && (
                                                            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Reason for rejection: {item.justification}</Typography>
                                                        )}
                                                    </CardContent>
                                                    <CardActions sx={{ justifyContent: 'flex-end' }}>
                                                        {sectionKey === 'rejected' && (<Button size="small" color="primary" variant='outlined' onClick={() => onRemove(item.id)}>Re-evaluate</Button>)}
                                                        {(sectionKey === 'manual' || sectionKey === 'accepted') && (<Button size="small" color="error" variant='contained' onClick={() => onRemove(item.id)}>Remove</Button>)}
                                                        {sectionKey === 'pending' && (
                                                            <>
                                                                <Button size="small" variant='contained' color="error" onClick={() => onReject(item)}>Reject</Button>
                                                                <Button size="small" variant='contained' color="success" onClick={() => onAccept(item.id)}>Accept</Button>
                                                            </>
                                                        )}
                                                    </CardActions>
                                                </Card>
                                            </ListItem>
                                        ))}
                                    </List>
                                </AccordionDetails>
                            </Accordion>
                        );
                    })}
                </Box>
            ) : (
                <Typography sx={{ p: 2, color: 'text.secondary' }}>No redactions or suggestions yet.</Typography>
            )}
        </Box>
    );
}