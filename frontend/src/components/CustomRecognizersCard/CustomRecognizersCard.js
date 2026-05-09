"use client";

import React, { useCallback, useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Dialog,
    DialogContent,
    DialogTitle,
    Divider,
    FormControl,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    Slider,
    Switch,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useSession } from "@/contexts/SessionContext";
import toast from 'react-hot-toast';
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import {
    createCustomRecognizer,
    deleteCustomRecognizer,
    getCustomRecognizers,
    updateCustomRecognizer,
    validateRegex,
} from '@/services/recognizerService';

const ENTITY_TYPE_LABELS = {
    THIRD_PARTY: 'Third-Party PII',
    OPERATIONAL: 'Operational Data',
};

const EMPTY_PATTERN = { name: '', regex: '', score: 0.85 };
const EMPTY_DENY_ITEM = { value: '' };

const emptyForm = () => ({
    name: '',
    description: '',
    entity_type: 'THIRD_PARTY',
    patterns: [{ ...EMPTY_PATTERN }],
    deny_list: [],
    mode: 'pattern', // 'pattern' | 'deny_list'
});

// --- Regex tester (debounced) ---
const RegexTester = ({ pattern }) => {
    const [sampleText, setSampleText] = useState('');
    const [result, setResult] = useState(null);
    const timerRef = useRef(null);

    const run = useCallback(async (pat, text) => {
        if (!pat || !text) { setResult(null); return; }
        try {
            const res = await validateRegex(pat, text);
            setResult(res);
        } catch {
            setResult({ valid: false, error: 'Network error — could not validate pattern.' });
        }
    }, []);

    useEffect(() => {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => run(pattern, sampleText), 400);
        return () => clearTimeout(timerRef.current);
    }, [pattern, sampleText, run]);

    const renderHighlighted = () => {
        if (!result?.valid || !result.matches?.length) return sampleText;
        const parts = [];
        let cursor = 0;
        for (const m of result.matches) {
            if (m.start > cursor) parts.push(sampleText.slice(cursor, m.start));
            parts.push(
                <mark key={m.start} style={{ backgroundColor: 'rgba(255,214,10,0.6)', borderRadius: 2 }}>
                    {sampleText.slice(m.start, m.end)}
                </mark>
            );
            cursor = m.end;
        }
        if (cursor < sampleText.length) parts.push(sampleText.slice(cursor));
        return parts;
    };

    return (
        <Box sx={{ mt: 2, p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Regex tester
            </Typography>
            <TextField
                label="Sample text"
                value={sampleText}
                onChange={(e) => setSampleText(e.target.value)}
                fullWidth
                multiline
                minRows={2}
                size="small"
                sx={{ mt: 1 }}
                slotProps={{ htmlInput: { 'aria-label': 'sample text for regex tester' } }}
            />
            {result && !result.valid && (
                <Alert severity="error" sx={{ mt: 1 }}>{result.error}</Alert>
            )}
            {result?.valid && sampleText && (
                <Box sx={{ mt: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1, fontFamily: 'monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {result.matches?.length > 0
                        ? renderHighlighted()
                        : <Typography variant="caption" color="text.secondary">No matches</Typography>
                    }
                </Box>
            )}
        </Box>
    );
};

// --- Add / Edit form ---
const RecognizerForm = ({ initial, onSave, onCancel }) => {
    const [form, setForm] = useState(initial || emptyForm());
    const [submitting, setSubmitting] = useState(false);

    const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));

    const addPatternRow = () => set('patterns', [...form.patterns, { ...EMPTY_PATTERN }]);
    const removePatternRow = (i) => set('patterns', form.patterns.filter((_, idx) => idx !== i));
    const updatePattern = (i, field, value) => set('patterns',
        form.patterns.map((p, idx) => idx === i ? { ...p, [field]: value } : p)
    );

    const addDenyItem = () => set('deny_list', [...form.deny_list, { ...EMPTY_DENY_ITEM }]);
    const removeDenyItem = (i) => set('deny_list', form.deny_list.filter((_, idx) => idx !== i));
    const updateDenyItem = (i, value) => set('deny_list',
        form.deny_list.map((d, idx) => idx === i ? { value } : d)
    );

    const handleModeChange = (mode) => {
        setForm(prev => ({
            ...prev,
            mode,
            patterns: mode === 'pattern' ? (prev.patterns.length ? prev.patterns : [{ ...EMPTY_PATTERN }]) : [],
            deny_list: mode === 'deny_list' ? (prev.deny_list.length ? prev.deny_list : [{ ...EMPTY_DENY_ITEM }]) : [],
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            const payload = {
                name: form.name.trim(),
                description: form.description.trim(),
                entity_type: form.entity_type,
                patterns: form.mode === 'pattern' ? form.patterns.filter(p => p.regex.trim()) : [],
                deny_list: form.mode === 'deny_list' ? form.deny_list.filter(d => d.value.trim()) : [],
            };
            await onSave(payload);
        } finally {
            setSubmitting(false);
        }
    };

    const testPattern = form.mode === 'pattern' && form.patterns.find(p => p.regex.trim())?.regex || '';

    return (
        <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
                label="Name"
                value={form.name}
                onChange={(e) => set('name', e.target.value)}
                required
                fullWidth
                size="small"
                autoFocus
                slotProps={{ htmlInput: { 'aria-label': 'recognizer name' } }}
            />
            <TextField
                label="Description (optional)"
                value={form.description}
                onChange={(e) => set('description', e.target.value)}
                fullWidth
                size="small"
                slotProps={{ htmlInput: { 'aria-label': 'recognizer description' } }}
            />
            <FormControl size="small" fullWidth required>
                <InputLabel>Entity type</InputLabel>
                <Select
                    label="Entity type"
                    value={form.entity_type}
                    onChange={(e) => set('entity_type', e.target.value)}
                    inputProps={{ 'aria-label': 'entity type' }}
                >
                    {Object.entries(ENTITY_TYPE_LABELS).map(([val, label]) => (
                        <MenuItem key={val} value={val}>{label}</MenuItem>
                    ))}
                </Select>
            </FormControl>

            <FormControl size="small" fullWidth>
                <InputLabel>Recognizer type</InputLabel>
                <Select
                    label="Recognizer type"
                    value={form.mode}
                    onChange={(e) => handleModeChange(e.target.value)}
                    inputProps={{ 'aria-label': 'recognizer type' }}
                >
                    <MenuItem value="pattern">Regex patterns</MenuItem>
                    <MenuItem value="deny_list">Deny list</MenuItem>
                </Select>
            </FormControl>

            {form.mode === 'pattern' && (
                <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Patterns
                    </Typography>
                    {form.patterns.map((p, i) => (
                        <Box key={i} sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', mt: 1 }}>
                            <TextField
                                label="Regex"
                                value={p.regex}
                                onChange={(e) => updatePattern(i, 'regex', e.target.value)}
                                size="small"
                                sx={{ flex: 2 }}
                                required
                                slotProps={{ htmlInput: { 'aria-label': `pattern regex ${i + 1}` } }}
                            />
                            <TextField
                                label="Name (opt.)"
                                value={p.name}
                                onChange={(e) => updatePattern(i, 'name', e.target.value)}
                                size="small"
                                sx={{ flex: 1 }}
                                slotProps={{ htmlInput: { 'aria-label': `pattern name ${i + 1}` } }}
                            />
                            <Box sx={{ flex: 1, minWidth: 80 }}>
                                <Typography variant="caption">Score: {p.score.toFixed(2)}</Typography>
                                <Slider
                                    value={p.score}
                                    onChange={(_, v) => updatePattern(i, 'score', v)}
                                    min={0.1}
                                    max={1.0}
                                    step={0.05}
                                    size="small"
                                    aria-label={`pattern score ${i + 1}`}
                                />
                            </Box>
                            <IconButton
                                size="small"
                                onClick={() => removePatternRow(i)}
                                disabled={form.patterns.length === 1}
                                aria-label={`remove pattern ${i + 1}`}
                            >
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Box>
                    ))}
                    <Button size="small" startIcon={<AddIcon />} onClick={addPatternRow} sx={{ mt: 1 }}>
                        Add pattern
                    </Button>
                    {testPattern && <RegexTester pattern={testPattern} />}
                </Box>
            )}

            {form.mode === 'deny_list' && (
                <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Deny-list terms
                    </Typography>
                    {form.deny_list.map((d, i) => (
                        <Box key={i} sx={{ display: 'flex', gap: 1, mt: 1 }}>
                            <TextField
                                label="Value"
                                value={d.value}
                                onChange={(e) => updateDenyItem(i, e.target.value)}
                                size="small"
                                fullWidth
                                required
                                slotProps={{ htmlInput: { 'aria-label': `deny list value ${i + 1}` } }}
                            />
                            <IconButton
                                size="small"
                                onClick={() => removeDenyItem(i)}
                                disabled={form.deny_list.length === 1}
                                aria-label={`remove deny list item ${i + 1}`}
                            >
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Box>
                    ))}
                    <Button size="small" startIcon={<AddIcon />} onClick={addDenyItem} sx={{ mt: 1 }}>
                        Add term
                    </Button>
                </Box>
            )}

            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', pt: 1 }}>
                <Button type="submit" variant="contained" disabled={!form.name.trim() || submitting}>
                    {submitting ? <CircularProgress size={20} color="inherit" /> : 'Save'}
                </Button>
                <Button onClick={onCancel}>Cancel</Button>
            </Box>
        </Box>
    );
};

// --- Main card ---
export const CustomRecognizersCard = () => {
    const { session } = useSession();

    const { data: recognizers, error, isLoading, mutate } = useSWR(
        session?.user?.id ? ['custom-recognizers'] : null,
        () => getCustomRecognizers()
    );

    const [manageOpen, setManageOpen] = useState(false);
    const [editTarget, setEditTarget] = useState(null); // null = add, obj = edit
    const [formOpen, setFormOpen] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(null);
    const [toggling, setToggling] = useState(null);

    const openAdd = () => { setEditTarget(null); setFormOpen(true); };
    const openEdit = (rec) => {
        const mode = rec.deny_list?.length > 0 && rec.patterns?.length === 0 ? 'deny_list' : 'pattern';
        setEditTarget({
            ...rec,
            mode,
        });
        setFormOpen(true);
    };
    const closeForm = () => { setFormOpen(false); setEditTarget(null); };

    const handleSave = async (payload) => {
        try {
            if (editTarget) {
                await updateCustomRecognizer(editTarget.id, payload);
                toast.success('Recognizer updated.');
            } else {
                await createCustomRecognizer(payload);
                toast.success('Recognizer created.');
            }
            await mutate();
            closeForm();
        } catch (e) {
            toast.error(e.message || 'Failed to save recognizer.');
        }
    };

    const handleToggle = async (rec) => {
        setToggling(rec.id);
        try {
            await updateCustomRecognizer(rec.id, { is_active: !rec.is_active });
            await mutate();
        } catch (e) {
            toast.error('Failed to toggle recognizer.');
        } finally {
            setToggling(null);
        }
    };

    const handleDelete = async () => {
        const id = confirmDelete.id;
        setConfirmDelete(null);
        try {
            await deleteCustomRecognizer(id);
            toast.success('Recognizer deleted.');
            await mutate();
        } catch (e) {
            toast.error('Failed to delete recognizer.');
        }
    };

    const count = recognizers?.length ?? 0;
    const activeCount = recognizers?.filter(r => r.is_active).length ?? 0;

    const formInitial = editTarget
        ? {
            name: editTarget.name,
            description: editTarget.description || '',
            entity_type: editTarget.entity_type,
            mode: editTarget.mode,
            patterns: editTarget.patterns?.length > 0 ? editTarget.patterns : [{ ...EMPTY_PATTERN }],
            deny_list: editTarget.deny_list?.length > 0 ? editTarget.deny_list : [{ ...EMPTY_DENY_ITEM }],
        }
        : null;

    return (
        <>
            <ConfirmationDialog
                open={!!confirmDelete}
                onClose={() => setConfirmDelete(null)}
                onConfirm={handleDelete}
                title="Delete Custom Recognizer"
                description={`Delete "${confirmDelete?.name}"? This will stop matching its patterns on future documents.`}
                confirmLabel="Delete"
                confirmColor="error"
            />

            {/* Manage list dialog */}
            <Dialog open={manageOpen && !formOpen} onClose={() => setManageOpen(false)} maxWidth="md" fullWidth>
                <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    Custom Recognizers
                    <IconButton aria-label="close" onClick={() => setManageOpen(false)} size="small">
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
                        <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
                            Add recognizer
                        </Button>
                    </Box>
                    {isLoading && (
                        <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}>
                            <CircularProgress />
                        </Box>
                    )}
                    {error && <Alert severity="error">Failed to load recognizers.</Alert>}
                    {recognizers && recognizers.length === 0 && (
                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                            No custom recognizers configured.
                        </Typography>
                    )}
                    {recognizers && recognizers.length > 0 && (
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Entity type</TableCell>
                                    <TableCell>Patterns / Terms</TableCell>
                                    <TableCell>Active</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {recognizers.map(rec => (
                                    <TableRow key={rec.id}>
                                        <TableCell>
                                            <Typography variant="body2">{rec.name}</Typography>
                                            {rec.description && (
                                                <Typography variant="caption" color="text.secondary">
                                                    {rec.description}
                                                </Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={ENTITY_TYPE_LABELS[rec.entity_type] || rec.entity_type}
                                                size="small"
                                            />
                                        </TableCell>
                                        <TableCell>
                                            {rec.patterns?.length > 0 && (
                                                <Typography variant="caption">{rec.patterns.length} pattern{rec.patterns.length !== 1 ? 's' : ''}</Typography>
                                            )}
                                            {rec.deny_list?.length > 0 && (
                                                <Typography variant="caption">{rec.deny_list.length} term{rec.deny_list.length !== 1 ? 's' : ''}</Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Tooltip title={rec.is_active ? 'Disable' : 'Enable'}>
                                                <Switch
                                                    checked={rec.is_active}
                                                    onChange={() => handleToggle(rec)}
                                                    disabled={toggling === rec.id}
                                                    size="small"
                                                    inputProps={{ 'aria-label': `toggle ${rec.name}` }}
                                                />
                                            </Tooltip>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Tooltip title="Edit">
                                                <IconButton size="small" onClick={() => openEdit(rec)} aria-label={`edit ${rec.name}`}>
                                                    <EditIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Delete">
                                                <IconButton size="small" color="error" onClick={() => setConfirmDelete(rec)} aria-label={`delete ${rec.name}`}>
                                                    <DeleteIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </DialogContent>
            </Dialog>

            {/* Add / Edit dialog */}
            <Dialog open={formOpen} onClose={closeForm} maxWidth="sm" fullWidth>
                <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    {editTarget ? 'Edit Recognizer' : 'Add Recognizer'}
                    <IconButton aria-label="close form" onClick={closeForm} size="small">
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ pt: 1 }}>
                        <RecognizerForm
                            initial={formInitial}
                            onSave={handleSave}
                            onCancel={closeForm}
                        />
                    </Box>
                </DialogContent>
            </Dialog>

            {/* Summary card */}
            <Card>
                <CardContent>
                    <Typography variant="h6" component="h2">
                        Custom Recognizers
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Domain-specific regex patterns and deny-list terms applied during extraction.
                    </Typography>
                    {recognizers && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {count} {count === 1 ? 'recognizer' : 'recognizers'} · {activeCount} active
                        </Typography>
                    )}
                    <Button variant="outlined" onClick={() => setManageOpen(true)}>
                        Manage
                    </Button>
                </CardContent>
            </Card>
        </>
    );
};
