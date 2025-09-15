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
    Tooltip
} from '@mui/material';

function formatScore(score) {
    return score ? (score * 100).toFixed(2) + '%' : 'N/A';
}

export default function TrainingRunList({ runs }) {
    return (
        <Paper sx={{ p: 3, mt: 4 }}>
            <Typography variant="h6" gutterBottom>Training Run History</Typography>
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