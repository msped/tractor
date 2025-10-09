"use client"

import React from 'react';
import {
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
    Tooltip,
    Box,
    IconButton
} from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';

function formatScore(score) {
    return score ? (score * 100).toFixed(2) + '%' : 'N/A';
}

const scoreExplanation = (
    <React.Fragment>
        <Typography color="inherit" variant="body2" sx={{ mb: 1 }}>These scores evaluate the model&#39;s performance. Scores closer to 100% are better.</Typography>
        <Box component="ul" sx={{ p: 0, m: 0, pl: 2 }}>
            <Box component="li" sx={{ mb: 0.5, fontSize: '0.8rem' }}><strong>P (Precision):</strong> Of all the redactions the model suggested, what percentage were correct?</Box>
            <Box component="li" sx={{ mb: 0.5, fontSize: '0.8rem' }}><strong>R (Recall):</strong> Of all the redactions that should have been made, what percentage did the model find?</Box>
            <Box component="li" sx={{ mb: 0.5, fontSize: '0.8rem' }}><strong>F1-Score:</strong> A balanced measure of Precision and Recall.</Box>
        </Box>
    </React.Fragment>
);

export const TrainingRunList = ({ runs }) => {
    return (
        <Paper sx={{ p: 3, mt: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">Training Run History</Typography>
                <Tooltip title={scoreExplanation}>
                    <IconButton size="small" sx={{ ml: 0.5 }}>
                        <HelpOutlineIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
            </Box>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>Date</TableCell>
                            <TableCell>Model Name</TableCell>
                            <TableCell>Source</TableCell>
                            <Tooltip title="F1-Score">
                                <TableCell align="right">F1</TableCell>
                            </Tooltip>
                            <Tooltip title="Precision">
                                <TableCell align="right">P</TableCell>
                            </Tooltip>
                            <Tooltip title="Recall">
                                <TableCell align="right">R</TableCell>
                            </Tooltip>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {runs.map((run) => (
                            <TableRow key={run.id} hover>
                                <TableCell>{new Date(run.created_at).toLocaleString()}</TableCell>
                                <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{run.model_name}</TableCell>
                                <TableCell>{run.source.replace('_', ' ')}</TableCell>
                                <TableCell align="right">{formatScore(run.f1_score)}</TableCell>
                                <TableCell align="right">{formatScore(run.precision)}</TableCell>
                                <TableCell align="right">{formatScore(run.recall)}</TableCell>
                            </TableRow>
                        ))}
                        {runs.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={6} align="center">
                                    No training runs found.
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
}