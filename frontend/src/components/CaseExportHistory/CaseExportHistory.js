"use client";

import React from 'react';
import useSWR from 'swr';
import {
    Box,
    Divider,
    IconButton,
    List,
    ListItem,
    ListItemText,
    Paper,
    Tooltip,
    Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import toast from 'react-hot-toast';

import { getCaseExports } from '@/services/caseService';
import { downloadFile } from '@/utils/downloadFile';

const formatTimestamp = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString();
};

export const CaseExportHistory = ({ caseData }) => {
    // Re-fetch whenever an export completes so a freshly generated disclosure
    // appears without a manual reload.
    const { data: exports } = useSWR(
        caseData?.id
            ? [`/cases/${caseData.id}/exports`, caseData.export_status]
            : null,
        () => getCaseExports(caseData.id)
    );

    const handleDownload = async (exportItem) => {
        try {
            await downloadFile(
                exportItem.export_file,
                `disclosure_package_${caseData.case_reference}_${exportItem.sequence}.zip`
            );
        } catch (error) {
            toast.error('Failed to download the export package.', {
                id: 'export-history-toast',
            });
        }
    };

    return (
        <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
                Disclosure History
            </Typography>
            <Divider />
            {!exports || exports.length === 0 ? (
                <Box sx={{ py: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                        No disclosures have been generated for this case yet.
                    </Typography>
                </Box>
            ) : (
                <List disablePadding>
                    {exports.map((exportItem) => (
                        <ListItem
                            key={exportItem.id}
                            divider
                            secondaryAction={
                                <Tooltip title="Download this disclosure">
                                    <IconButton
                                        edge="end"
                                        aria-label={`Download ${exportItem.label}`}
                                        onClick={() => handleDownload(exportItem)}
                                    >
                                        <DownloadIcon />
                                    </IconButton>
                                </Tooltip>
                            }
                        >
                            <ListItemText
                                primary={exportItem.label}
                                secondary={formatTimestamp(exportItem.created_at)}
                            />
                        </ListItem>
                    ))}
                </List>
            )}
        </Paper>
    );
};
