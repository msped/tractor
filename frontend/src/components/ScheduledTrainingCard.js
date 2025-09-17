"use client"

import React, { useState } from 'react';
import {
    CardContent, Typography, Box, Chip, Button, IconButton, Tooltip, Dialog, DialogTitle,
    DialogContent, DialogActions, Select, MenuItem, FormControl, InputLabel, TextField
} from '@mui/material';
import ScheduleIcon from '@mui/icons-material/Schedule';
import DeleteIcon from '@mui/icons-material/Delete';
import { createTrainingSchedule, deleteTrainingSchedule } from '@/services/trainingService';
import toast from 'react-hot-toast';

export default function ScheduledTrainingCard({ schedule }) {
    const getTomorrowAt9AM = () => {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(9, 0, 0, 0);
        // Format for datetime-local input: YYYY-MM-DDTHH:mm
        return tomorrow.toISOString().slice(0, 16);
    };

    const [dialogOpen, setDialogOpen] = useState(false);
    const [frequency, setFrequency] = useState('W');
    const [nextRun, setNextRun] = useState(getTomorrowAt9AM());

    const handleOpenDialog = () => {
        setNextRun(getTomorrowAt9AM());
        setDialogOpen(true);
    };

    const handleCreateSchedule = async () => {
        const toastId = toast.loading("Creating schedule...");
        try {
            await createTrainingSchedule({
                func: 'training.tasks.train_model',
                schedule_type: frequency, repeats: -1, // Repeat indefinitely
                next_run: new Date(nextRun).toISOString()
            });
            toast.success("Training schedule created successfully.", { id: toastId });
        } catch (error) {
            toast.error(error.message, { id: toastId });
        } finally {
            setDialogOpen(false);
        }
    };

    const handleDeleteSchedule = async () => {
        if (!schedule) return;
        const toastId = toast.loading("Deleting schedule...");
        try {
            await deleteTrainingSchedule(schedule.id);
            toast.success("Training schedule deleted.", { id: toastId });
        } catch (error) {
            toast.error(error.message, { id: toastId });
        }
    };

    return (
        <>
            <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <ScheduleIcon color="action" sx={{ mr: 1 }} />
                    <Typography variant="h6" component="h2">Automated Training Schedule</Typography>
                </Box>
                {schedule ? (
                    <>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            The model is scheduled to retrain automatically to learn from new redactions.
                        </Typography>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 2 }}>
                            <Typography>Next scheduled run:</Typography>
                            <Chip label={new Date(schedule.next_run).toLocaleString()} color="primary" variant="outlined" />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                            <Tooltip title="Delete Schedule">
                                <IconButton onClick={handleDeleteSchedule} size="small"><DeleteIcon /></IconButton>
                            </Tooltip>
                        </Box>
                    </>
                ) : (
                    <>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            No automated training schedule is currently active. Create one to automatically improve the model over time.
                        </Typography>
                        <Button variant="contained" onClick={handleOpenDialog}>Schedule Training</Button>
                    </>
                )}
            </CardContent>
            <Dialog open={dialogOpen} maxWidth="xs" fullWidth onClose={() => setDialogOpen(false)}>
                <DialogTitle>Create New Training Schedule</DialogTitle>
                <DialogContent>
                    <FormControl fullWidth sx={{ mt: 2 }}>
                        <InputLabel id="frequency-select-label">Frequency</InputLabel>
                        <Select
                            labelId="frequency-select-label"
                            value={frequency}
                            label="Frequency"
                            onChange={(e) => setFrequency(e.target.value)}
                        >
                            <MenuItem value={'W'}>Weekly</MenuItem>
                            <MenuItem value={'M'}>Monthly</MenuItem>
                            <MenuItem value={'Q'}>Quarterly</MenuItem>
                            <MenuItem value={'Y'}>Yearly</MenuItem>
                        </Select>
                    </FormControl>
                    <TextField
                        margin="dense"
                        id="next_run"
                        label="First Run Time"
                        type="datetime-local"
                        fullWidth
                        value={nextRun}
                        onChange={(e) => setNextRun(e.target.value)}
                        slotProps={{ 
                            input: { shrink: "true"}
                        }}
                        sx={{ mt: 3 }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
                    <Button onClick={handleCreateSchedule} variant="contained">Create</Button>
                </DialogActions>
            </Dialog>
        </>
    );
}