import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, Accordion, AccordionSummary, AccordionDetails, List, ListItem, Card, CardContent, CardActions, Button, Chip, ButtonGroup, Menu, MenuItem } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import { RedactionContextManager } from '../RedactionContextManager.js';

const REDACTION_TYPE_LABELS = {
    'PII': 'Third-Party PII',
    'OP_DATA': 'Operational Data',
    'DS_INFO': 'Data Subject Information',
};

const getRedactionTypeLabel = (type) => REDACTION_TYPE_LABELS[type] || 'Suggestion';

const truncateText = (text, maxLength = 23) => {
    if (!text || text.length <= maxLength) {
        return text;
    }
    return text.substring(0, maxLength) + '...';
};

export const RedactionSidebar = ({
    redactions,
    onAccept,
    onReject,
    onRemove,
    onChangeTypeAndAccept,
    onSuggestionMouseEnter,
    onSuggestionMouseLeave,
    scrollToId,
    removeScrollId,
    onContextSave,
}) => {
    const { rejected, accepted, pending, manual } = redactions;
    const redactionSections = Object.keys(redactions);
    const [expanded, setExpanded] = useState(new Set(['pending']));
    const [editingContextId, setEditingContextId] = useState(null);
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

    const [menuAnchorEl, setMenuAnchorEl] = useState(null);
    const [currentItemForMenu, setCurrentItemForMenu] = useState(null);

    const handleMenuClick = (event, item) => {
        setMenuAnchorEl(event.currentTarget);
        setCurrentItemForMenu(item);
    };

    const handleMenuClose = () => {
        setMenuAnchorEl(null);
        setCurrentItemForMenu(null);
    };

    const handleTypeChange = (newType) => {
        onChangeTypeAndAccept(currentItemForMenu.id, newType);
        handleMenuClose();
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
        <Box sx={{ width: '100%', borderLeft: 1, borderColor: 'divider', height: 'calc(100vh - 64px)', overflowY: 'auto', bgcolor: 'background.default' }}>
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', position: 'sticky', top: 0, bgcolor: 'background.paper', zIndex: 1 }}>
                <Typography variant="h6" component='h2' color='text.primary'>Redactions</Typography>
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
                                                    <CardActions sx={{ justifyContent: (sectionKey === 'accepted' || sectionKey === 'manual') ? 'space-between' : 'flex-end' }}>
                                                        {(sectionKey === 'accepted' || sectionKey === 'manual') &&
                                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                                <Button startIcon={item.context ? <EditIcon /> : <AddIcon />} variant="text" size='small' onClick={() => setEditingContextId(item.id)}>
                                                                    Context
                                                                </Button>
                                                                {item.context?.text && (
                                                                    <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>{`"${truncateText(item.context.text)}"`}</Typography>
                                                                )}
                                                            </Box>
                                                        }
                                                        {sectionKey === 'rejected' && (<Button size="small" color="primary" variant='outlined' onClick={() => onRemove(item.id)}>Re-evaluate</Button>)}
                                                        {(sectionKey === 'manual' || sectionKey === 'accepted') && (<Button size="small" color="error" variant='contained' onClick={() => onRemove(item.id)}>Remove</Button>)}
                                                        {sectionKey === 'pending' &&
                                                            <Box sx={{ display: 'flex', gap: 1 }}>
                                                                <Button size="small" variant='contained' color="error" onClick={() => onReject(item)}>Reject</Button>
                                                                <ButtonGroup variant="contained" color="success" size="small">
                                                                    <Button onClick={() => onAccept(item.id)}>Accept</Button>
                                                                    <Button
                                                                        aria-controls={menuAnchorEl ? 'split-button-menu' : undefined}
                                                                        aria-expanded={menuAnchorEl ? 'true' : undefined}
                                                                        aria-label="change redaction type and accept"
                                                                        aria-haspopup="menu"
                                                                        onClick={(e) => handleMenuClick(e, item)}
                                                                    >
                                                                        <ArrowDropDownIcon />
                                                                    </Button>
                                                                </ButtonGroup>
                                                            </Box>
                                                        }
                                                    </CardActions>
                                                    {(sectionKey === 'accepted' || sectionKey === 'manual') && (
                                                        <div data-testid={`redaction-context-manager-${item.id}`}>
                                                        <RedactionContextManager
                                                            redactionId={item.id}
                                                            context={item.context}
                                                            isEditing={editingContextId === item.id}
                                                            onCancel={() => setEditingContextId(null)}
                                                            onContextSave={onContextSave}
                                                        />
                                                        </div>
                                                    )}
                                                </Card>
                                            </ListItem>
                                        ))}
                                    </List>
                                </AccordionDetails>
                            </Accordion>
                        );
                    })}
                    <Menu
                        id="split-button-menu"
                        anchorEl={menuAnchorEl}
                        open={Boolean(menuAnchorEl)}
                        onClose={handleMenuClose}
                    >
                        {Object.keys(REDACTION_TYPE_LABELS)
                            .filter(typeKey => typeKey !== currentItemForMenu?.redaction_type)
                            .map(typeKey => (
                                <MenuItem key={typeKey} onClick={() => handleTypeChange(typeKey)}>
                                    Accept as {REDACTION_TYPE_LABELS[typeKey]}
                                </MenuItem>
                            ))}
                    </Menu>
                </Box>
            ) : (
                <Typography sx={{ p: 2, color: 'text.secondary' }}>No redactions or suggestions yet.</Typography>
            )}
        </Box>
    );
}