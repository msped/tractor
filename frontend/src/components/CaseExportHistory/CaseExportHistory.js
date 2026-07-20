"use client";

import React, { useState } from 'react';
import useSWR from 'swr';
import {
    Box,
    Chip,
    CircularProgress,
    Collapse,
    Divider,
    IconButton,
    Paper,
    Tooltip,
    Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import toast from 'react-hot-toast';

import {
    getCaseDisclosureDiff,
    getCaseExports,
    getExportDiff,
} from '@/services/caseService';
import { downloadFile } from '@/utils/downloadFile';
import { DisclosureDiffView } from '@/components/DisclosureDiffView';

const formatTimestamp = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString();
};

const DiffPanel = ({ swrKey, fetcher, expanded }) => {
    const { data, error } = useSWR(expanded ? swrKey : null, fetcher);
    if (error) {
        return (
            <Typography variant="body2" color="text.secondary">
                Change details are unavailable for this disclosure.
            </Typography>
        );
    }
    if (!data) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
                <CircularProgress size={20} />
            </Box>
        );
    }
    return <DisclosureDiffView diff={data} />;
};

const ReviewOutcome = ({ review }) => {
    if (!review) return null;
    const attribution = [review.closed_by, formatTimestamp(review.closed_at)]
        .filter(Boolean)
        .join(' · ');
    return (
        <Box sx={{ mb: 1.5 }}>
            <Typography variant="subtitle2">Review outcome</Typography>
            <Typography
                variant="body2"
                color="text.secondary"
                sx={{ whiteSpace: 'pre-wrap' }}
            >
                {review.outcome || '—'}
            </Typography>
            {attribution && (
                <Typography variant="caption" color="text.secondary">
                    {attribution}
                </Typography>
            )}
        </Box>
    );
};

const ExpandToggle = ({ expanded, onToggle }) => (
    <IconButton
        size="small"
        onClick={onToggle}
        aria-label={expanded ? 'Collapse' : 'Expand'}
    >
        <ExpandMoreIcon
            sx={{
                transform: expanded ? 'rotate(180deg)' : 'none',
                transition: 'transform 0.2s',
            }}
        />
    </IconButton>
);

const DisclosureRow = ({ caseData, exportItem }) => {
    const [expanded, setExpanded] = useState(false);
    const toggle = () => setExpanded((value) => !value);

    const handleDownload = async (event) => {
        event.stopPropagation();
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
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
                <ExpandToggle expanded={expanded} onToggle={toggle} />
                <Box sx={{ flexGrow: 1, cursor: 'pointer' }} onClick={toggle}>
                    <Typography variant="body1">{exportItem.label}</Typography>
                    <Typography variant="caption" color="text.secondary">
                        {formatTimestamp(exportItem.created_at)}
                    </Typography>
                </Box>
                {exportItem.review_detail && (
                    <Chip size="small" variant="outlined" label="From review" />
                )}
                <Tooltip title="Download this disclosure">
                    <IconButton
                        aria-label={`Download ${exportItem.label}`}
                        onClick={handleDownload}
                    >
                        <DownloadIcon />
                    </IconButton>
                </Tooltip>
            </Box>
            <Collapse in={expanded} unmountOnExit>
                <Box sx={{ pl: 5, pr: 2, pb: 2 }}>
                    <ReviewOutcome review={exportItem.review_detail} />
                    <DiffPanel
                        swrKey={[
                            `/cases/${caseData.id}/exports/${exportItem.id}/diff`,
                        ]}
                        fetcher={() =>
                            getExportDiff(caseData.id, exportItem.id)
                        }
                        expanded={expanded}
                    />
                </Box>
            </Collapse>
        </Box>
    );
};

const InProgressRow = ({ caseData }) => {
    const [expanded, setExpanded] = useState(false);
    const toggle = () => setExpanded((value) => !value);

    return (
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    py: 1,
                    cursor: 'pointer',
                }}
                onClick={toggle}
            >
                <ExpandToggle expanded={expanded} onToggle={toggle} />
                <Chip size="small" color="warning" label="In progress" />
                <Typography variant="body1">
                    Current review — changes not yet disclosed
                </Typography>
            </Box>
            <Collapse in={expanded} unmountOnExit>
                <Box sx={{ pl: 5, pr: 2, pb: 2 }}>
                    <DiffPanel
                        swrKey={[
                            `/cases/${caseData.id}/diff`,
                            caseData.export_status,
                        ]}
                        fetcher={() => getCaseDisclosureDiff(caseData.id)}
                        expanded={expanded}
                    />
                </Box>
            </Collapse>
        </Box>
    );
};

/**
 * The case's disclosure history: every preserved disclosure package, newest
 * first, each expandable to reveal the review outcome that produced it and the
 * redaction changes it introduced (diffed against the disclosure before it).
 * While a review is open, a leading "in progress" row previews the changes
 * staged for the next disclosure.
 */
export const CaseExportHistory = ({ caseData }) => {
    // Re-fetch whenever an export completes so a freshly generated disclosure
    // appears without a manual reload.
    const { data: exports } = useSWR(
        caseData?.id
            ? [`/cases/${caseData.id}/exports`, caseData.export_status]
            : null,
        () => getCaseExports(caseData.id)
    );

    const isUnderReview = caseData?.status === 'UNDER_REVIEW';
    const ordered = exports ? [...exports].reverse() : [];
    const hasExports = ordered.length > 0;

    return (
        <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
                Disclosure History
            </Typography>
            <Divider sx={{ mb: 1 }} />
            {isUnderReview && <InProgressRow caseData={caseData} />}
            {hasExports
                ? ordered.map((exportItem) => (
                      <DisclosureRow
                          key={exportItem.id}
                          caseData={caseData}
                          exportItem={exportItem}
                      />
                  ))
                : !isUnderReview && (
                      <Box sx={{ py: 2 }}>
                          <Typography variant="body2" color="text.secondary">
                              No disclosures have been generated for this case
                              yet.
                          </Typography>
                      </Box>
                  )}
        </Paper>
    );
};
