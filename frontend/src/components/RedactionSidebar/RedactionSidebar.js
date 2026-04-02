import React, { useState, useEffect, useRef } from 'react';
import { useSession } from 'next-auth/react';
import { getExemptionTemplates } from '@/services/redactionService';
import {
    Box, Typography, Accordion, AccordionSummary, AccordionDetails,
    List, ListItem, Card, CardContent, CardActions, Button, Chip,
    ButtonGroup, Menu, MenuItem, IconButton, Tooltip, TextField, Divider,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import CallSplitIcon from '@mui/icons-material/CallSplit';
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

const HIGHLIGHT_TOOLS = [
    { type: 'PII',     label: 'PII',        fullLabel: 'Third-Party PII',         color: 'rgb(46, 204, 113)'  },
    { type: 'OP_DATA', label: 'Op. Data',   fullLabel: 'Operational Data',         color: 'rgb(0, 221, 255)'   },
    { type: 'DS_INFO', label: 'DS Info',    fullLabel: 'Data Subject Information', color: 'rgb(177, 156, 217)' },
    { type: 'REMOVE',  label: 'Remove',     fullLabel: 'Remove Highlight',         color: 'rgb(231, 76, 60)'   },
];

export const RedactionSidebar = ({
    redactions,
    onAccept,
    onReject,
    onRemove,
    onChangeTypeAndAccept,
    onBulkChangeTypeAndAccept = () => {},
    onBulkAccept = () => {},
    onBulkReject = () => {},
    onRejectAsDisclosable = () => {},
    onSplitMerge = () => {},
    onSuggestionMouseEnter,
    onSuggestionMouseLeave,
    scrollToId,
    removeScrollId,
    onContextSave,
    onCardClick = () => {},
    activeHighlightType = null,
    onToggleHighlightTool = () => {},
    documentCompleted = false,
}) => {
    const { data: session } = useSession();
    const [exemptionTemplates, setExemptionTemplates] = useState([]);

    useEffect(() => {
        if (!session?.access_token) return;
        getExemptionTemplates(session.access_token)
            .then(setExemptionTemplates)
            .catch(() => {});
    }, [session?.access_token]);

    const redactionSections = Object.keys(redactions);
    const [expanded, setExpanded] = useState(new Set(['pending']));
    const [expandedGroups, setExpandedGroups] = useState(new Set());
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

    const toggleGroup = (key) => {
        setExpandedGroups(prev => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const [menuAnchorEl, setMenuAnchorEl] = useState(null);
    const [currentItemForMenu, setCurrentItemForMenu] = useState(null);
    const [rejectMenuAnchorEl, setRejectMenuAnchorEl] = useState(null);
    const [currentItemForRejectMenu, setCurrentItemForRejectMenu] = useState(null);
    const [exemptionSearch, setExemptionSearch] = useState('');

    const handleMenuClick = (event, item) => {
        setMenuAnchorEl(event.currentTarget);
        setCurrentItemForMenu(item);
    };

    const handleMenuClose = () => {
        setMenuAnchorEl(null);
        setCurrentItemForMenu(null);
    };

    const handleTypeChange = (newType) => {
        if (currentItemForMenu?.isMerged) {
            onBulkChangeTypeAndAccept(currentItemForMenu.ids, newType);
        } else {
            onChangeTypeAndAccept(currentItemForMenu.id || currentItemForMenu.ids?.[0], newType);
        }
        handleMenuClose();
    };

    // Helper: get all DB ids from a display item (single, merged, or group)
    const getAllIds = (item) => {
        if (item.isGroup) {
            return item.items.flatMap(gi => gi.ids || [gi.id]);
        }
        return item.ids || [item.id];
    };

    useEffect(() => {
        if (!scrollToId) return;

        const targetSection = redactionSections.find(key => {
            const sectionData = redactions[key];
            const items = sectionData?.items || (Array.isArray(sectionData) ? sectionData : []);
            return items.some(item => getAllIds(item).includes(scrollToId));
        });

        if (targetSection) {
            if (!expanded.has(targetSection)) {
                setExpanded(prev => new Set(prev).add(targetSection));
            }

            // If item is inside a collapsed group, expand the group too
            const sectionData = redactions[targetSection];
            const sectionItems = sectionData?.items || (Array.isArray(sectionData) ? sectionData : []);
            const parentGroup = sectionItems.find(item =>
                item.isGroup && item.items.some(gi => (gi.ids || [gi.id]).includes(scrollToId))
            );
            if (parentGroup && !expandedGroups.has(parentGroup.key)) {
                setExpandedGroups(prev => new Set(prev).add(parentGroup.key));
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
    }, [scrollToId, redactions, redactionSections, expanded, expandedGroups, removeScrollId]);

    const renderItem = (item, sectionKey) => {
        const ids = item.ids || [item.id];
        const itemKey = ids[0];
        const isMerged = item.isMerged || false;

        return (
            <ListItem
                key={itemKey}
                ref={el => ids.forEach(id => { itemRefs.current[id] = el; })}
                sx={{ px: 0, '&:not(:last-child)': { mb: 1 } }}
                onMouseEnter={() => onSuggestionMouseEnter(itemKey)}
                onMouseLeave={onSuggestionMouseLeave}
            >
                <Card variant="outlined" sx={{ width: '100%' }}>
                    <CardContent onClick={() => onCardClick(ids[0])} sx={{ cursor: 'pointer' }}>
                        <Typography variant="body2" sx={{ fontStyle: 'italic', mb: 2 }}>{`"${item.text}"`}</Typography>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                <Chip label={getRedactionTypeLabel(item.redaction_type)} size="small" />
                                {isMerged && (
                                    <Chip label={`merged (${ids.length})`} size="small" variant="outlined" />
                                )}
                            </Box>
                            <Typography variant="caption" color="text.secondary">Source: {item.is_suggestion ? 'AI' : 'User'}</Typography>
                        </Box>
                        {item.justification && (
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Reason for rejection: {item.justification}</Typography>
                        )}
                    </CardContent>
                    <CardActions sx={{ justifyContent: (sectionKey === 'accepted' || sectionKey === 'manual') ? 'space-between' : 'flex-end' }}>
                        {(sectionKey === 'accepted' || sectionKey === 'manual') &&
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Button startIcon={item.context ? <EditIcon /> : <AddIcon />} variant="text" size='small' onClick={() => setEditingContextId(itemKey)}>
                                    Context
                                </Button>
                                {item.context?.text && (
                                    <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>{`"${truncateText(item.context.text)}"`}</Typography>
                                )}
                            </Box>
                        }
                        {sectionKey === 'rejected' && (
                            <Button size="small" color="primary" variant='outlined' onClick={() => onRemove(item.id || itemKey)}>Re-evaluate</Button>
                        )}
                        {(sectionKey === 'manual' || sectionKey === 'accepted') && (
                            <Button size="small" color="error" variant='contained' onClick={() => onRemove(item.id || itemKey)}>Remove</Button>
                        )}
                        {sectionKey === 'pending' &&
                            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                                {isMerged && (
                                    <Tooltip title="Split into individual redactions">
                                        <IconButton
                                            size="small"
                                            onClick={() => onSplitMerge(ids.join(':'))}
                                            aria-label="split merged redaction"
                                        >
                                            <CallSplitIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                )}
                                {isMerged ? (
                                    <>
                                        <ButtonGroup variant="contained" color="error" size="small">
                                            <Button onClick={() => onBulkReject(ids)}>Reject</Button>
                                            <Button
                                                aria-label="reject with reason"
                                                aria-haspopup="menu"
                                                onClick={(e) => { setRejectMenuAnchorEl(e.currentTarget); setCurrentItemForRejectMenu({ ids }); }}
                                            >
                                                <ArrowDropDownIcon />
                                            </Button>
                                        </ButtonGroup>
                                        <ButtonGroup variant="contained" color="success" size="small">
                                            <Button onClick={() => onBulkAccept(ids)}>Accept</Button>
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
                                    </>
                                ) : (
                                    <>
                                        <ButtonGroup variant="contained" color="error" size="small">
                                            <Button onClick={() => onReject(item)}>Reject</Button>
                                            <Button
                                                aria-label="reject with reason"
                                                aria-haspopup="menu"
                                                onClick={(e) => { setRejectMenuAnchorEl(e.currentTarget); setCurrentItemForRejectMenu({ ids: [item.id || itemKey] }); }}
                                            >
                                                <ArrowDropDownIcon />
                                            </Button>
                                        </ButtonGroup>
                                        <ButtonGroup variant="contained" color="success" size="small">
                                            <Button onClick={() => onAccept(item.id || itemKey)}>Accept</Button>
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
                                    </>
                                )}
                            </Box>
                        }
                    </CardActions>
                    {(sectionKey === 'accepted' || sectionKey === 'manual') && (
                        <div data-testid={`redaction-context-manager-${itemKey}`}>
                            <RedactionContextManager
                                redactionId={itemKey}
                                context={item.context}
                                isEditing={editingContextId === itemKey}
                                onCancel={() => setEditingContextId(null)}
                                onContextSave={onContextSave}
                            />
                        </div>
                    )}
                </Card>
            </ListItem>
        );
    };

    const hasItems = redactionSections.some(key => {
        const sectionData = redactions[key];
        const total = sectionData?.total ?? (Array.isArray(sectionData) ? sectionData.length : 0);
        return total > 0;
    });

    return (
        <Box sx={{ width: '100%', borderLeft: 1, borderColor: 'divider', height: 'calc(100vh - 64px)', overflowY: 'auto', bgcolor: 'background.default' }}>
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', position: 'sticky', top: 0, bgcolor: 'background.paper', zIndex: 1 }}>
                <Typography variant="h6" component='h2' color='text.primary'>Redactions</Typography>
                {!documentCompleted && (
                    <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
                        {HIGHLIGHT_TOOLS.map(({ type, label, fullLabel, color }) => {
                            const isActive = activeHighlightType === type;
                            return (
                                <Tooltip key={type} title={isActive ? `Deactivate: ${fullLabel}` : type === 'REMOVE' ? `Click a highlight to remove it` : `Highlight as: ${fullLabel}`}>
                                    <Button
                                        size="small"
                                        variant="contained"
                                        onClick={() => onToggleHighlightTool(type)}
                                        sx={{
                                            flex: 1,
                                            backgroundColor: color,
                                            color: 'rgba(0,0,0,0.75)',
                                            opacity: isActive ? 1 : 0.45,
                                            outline: isActive ? `3px solid rgba(0,0,0,0.4)` : 'none',
                                            outlineOffset: '1px',
                                            fontWeight: isActive ? 'bold' : 'normal',
                                            '&:hover': {
                                                backgroundColor: color,
                                                opacity: 0.85,
                                            },
                                            boxShadow: 'none',
                                            minWidth: 0,
                                        }}
                                    >
                                        {label}
                                    </Button>
                                </Tooltip>
                            );
                        })}
                    </Box>
                )}
            </Box>
            {hasItems ? (
                <Box sx={{ py: 2 }}>
                    {redactionSections.map((sectionKey) => {
                        const sectionData = redactions[sectionKey];
                        const displayItems = sectionData?.items || (Array.isArray(sectionData) ? sectionData : []);
                        const total = sectionData?.total ?? displayItems.length;

                        if (total === 0) return null;

                        return (
                            <Accordion
                                key={sectionKey}
                                expanded={expanded.has(sectionKey)}
                                onChange={handleAccordionChange(sectionKey)}
                                disableGutters
                                sx={{ '&:not(:last-child)': { mb: 1 } }}
                            >
                                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                    <Typography sx={{ textTransform: 'capitalize' }}>{`${sectionKey} (${total})`}</Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <List dense sx={{ p: 0 }}>
                                        {displayItems.map(displayItem => {
                                            if (displayItem.isGroup) {
                                                const allIds = displayItem.items.flatMap(i => i.ids || [i.id]);
                                                const isGroupExpanded = expandedGroups.has(displayItem.key);

                                                return (
                                                    <ListItem
                                                        key={displayItem.key}
                                                        ref={el => {
                                                            displayItem.items.forEach(gi =>
                                                                (gi.ids || [gi.id]).forEach(id => { itemRefs.current[id] = el; })
                                                            );
                                                        }}
                                                        sx={{ px: 0, flexDirection: 'column', alignItems: 'stretch', '&:not(:last-child)': { mb: 1 } }}
                                                    >
                                                        <Card variant="outlined">
                                                            <CardContent sx={{ pb: 1, '&:last-child': { pb: 1 }, cursor: 'pointer' }} onClick={() => onCardClick(allIds[0])}>
                                                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                                    <Box>
                                                                        <Typography variant="body2" sx={{ fontStyle: 'italic' }}>{`"${displayItem.text}"`}</Typography>
                                                                        <Typography variant="caption" color="text.secondary">
                                                                            {getRedactionTypeLabel(displayItem.redaction_type)} · {displayItem.items.length} occurrences
                                                                        </Typography>
                                                                    </Box>
                                                                    <IconButton
                                                                        size="small"
                                                                        onClick={(e) => { e.stopPropagation(); toggleGroup(displayItem.key); }}
                                                                        aria-label={isGroupExpanded ? 'collapse group' : 'expand group'}
                                                                    >
                                                                        {isGroupExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                                                                    </IconButton>
                                                                </Box>
                                                            </CardContent>
                                                            {sectionKey === 'pending' && (
                                                                <CardActions sx={{ justifyContent: 'flex-end', pt: 0 }}>
                                                                    <ButtonGroup variant="contained" color="error" size="small">
                                                                        <Button onClick={() => onBulkReject(allIds)}>Reject All</Button>
                                                                        <Button
                                                                            aria-label="reject all with reason"
                                                                            aria-haspopup="menu"
                                                                            onClick={(e) => { setRejectMenuAnchorEl(e.currentTarget); setCurrentItemForRejectMenu({ ids: allIds }); }}
                                                                        >
                                                                            <ArrowDropDownIcon />
                                                                        </Button>
                                                                    </ButtonGroup>
                                                                    <ButtonGroup variant="contained" color="success" size="small">
                                                                        <Button onClick={() => onBulkAccept(allIds)}>Accept All</Button>
                                                                        <Button
                                                                            aria-controls={menuAnchorEl ? 'split-button-menu' : undefined}
                                                                            aria-expanded={menuAnchorEl ? 'true' : undefined}
                                                                            aria-label="change redaction type and accept all"
                                                                            aria-haspopup="menu"
                                                                            onClick={(e) => handleMenuClick(e, { ids: allIds, isMerged: true, redaction_type: displayItem.redaction_type })}
                                                                        >
                                                                            <ArrowDropDownIcon />
                                                                        </Button>
                                                                    </ButtonGroup>
                                                                </CardActions>
                                                            )}
                                                            {isGroupExpanded && (
                                                                <Box sx={{ borderTop: 1, borderColor: 'divider', bgcolor: 'action.hover', px: 1, pt: 0.5, pb: 0.5 }}>
                                                                    <List dense sx={{ p: 0 }}>
                                                                        {displayItem.items.map(gi => renderItem(gi, sectionKey))}
                                                                    </List>
                                                                </Box>
                                                            )}
                                                        </Card>
                                                    </ListItem>
                                                );
                                            }

                                            return renderItem(displayItem, sectionKey);
                                        })}
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
                    <Menu
                        anchorEl={rejectMenuAnchorEl}
                        open={Boolean(rejectMenuAnchorEl)}
                        onClose={() => { setRejectMenuAnchorEl(null); setCurrentItemForRejectMenu(null); setExemptionSearch(''); }}
                        slotProps={{ paper: { sx: { width: 280 } } }}
                    >
                        <Box sx={{ px: 1, pb: 1 }}>
                            <TextField
                                size="small"
                                placeholder="Search exemptions..."
                                value={exemptionSearch}
                                onChange={(e) => setExemptionSearch(e.target.value)}
                                onKeyDown={(e) => e.stopPropagation()}
                                autoFocus
                                fullWidth
                            />
                        </Box>
                        <Divider />
                        {exemptionTemplates
                            .filter(t => t.name.toLowerCase().includes(exemptionSearch.toLowerCase()))
                            .map(t => (
                                <MenuItem
                                    key={t.id}
                                    onClick={() => {
                                        onRejectAsDisclosable(currentItemForRejectMenu.ids, t.name);
                                        setRejectMenuAnchorEl(null);
                                        setCurrentItemForRejectMenu(null);
                                        setExemptionSearch('');
                                    }}
                                >
                                    {t.name}
                                </MenuItem>
                            ))
                        }
                        {exemptionTemplates.filter(t => t.name.toLowerCase().includes(exemptionSearch.toLowerCase())).length === 0 && (
                            <MenuItem disabled>No exemptions found</MenuItem>
                        )}
                    </Menu>
                </Box>
            ) : (
                <Typography sx={{ p: 2, color: 'text.secondary' }}>No redactions or suggestions yet.</Typography>
            )}
        </Box>
    );
}
