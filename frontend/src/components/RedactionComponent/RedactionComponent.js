"use client"

import React, { useState, useCallback, useMemo } from 'react';
import { Alert, Box, Typography, Button, Container, Tooltip, CircularProgress, IconButton, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from '@mui/material';
import TextDecreaseIcon from '@mui/icons-material/TextDecrease';
import TextIncreaseIcon from '@mui/icons-material/TextIncrease';
import RefreshIcon from '@mui/icons-material/Refresh';
import NextLink from 'next/link';
import { RedactionSidebar } from '@/components/RedactionSidebar';
import { ManualRedactionPopover } from '@/components/ManualRedactionPopover';
import { RejectReasonDialog } from '@/components/RejectReasonDialog';
import { ResubmitDialog } from '@/components/ResubmitDialog';
import { PropagationConfirmDialog } from '@/components/PropagationConfirmDialog';
import { getExemptionTemplates } from '@/services/redactionService';
import useSWR from 'swr';
import { DocumentViewer } from '@/components/DocumentViewer';
import { useRedactionState, getDocumentViewerProps, getRedactionSidebarProps } from '@/hooks/useRedactionState';
import { useRouter } from 'next/navigation';

const REDACTION_TYPE_LABELS = {
    PII: 'Third-Party PII',
    OP_DATA: 'Operational Data',
    DS_INFO: 'Data Subject Information',
};

export const RedactionComponent = ({ document: currentDocument, initialRedactions }) => {
    const router = useRouter();

    const { data: exemptionTemplates = [] } = useSWR(
        ['exemptions'],
        () => getExemptionTemplates(),
        { dedupingInterval: 60000 }
    );

    const store = useRedactionState({ document: currentDocument, initialRedactions, router });
    const { layout, document: docState, markAllInCase, rejectionDialog } = store;

    const isAutoAcceptMode = useMemo(
        () => initialRedactions.some(r => r.auto_accepted),
        [initialRedactions]
    );
    const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false);
    const handleScrolledToBottom = useCallback(() => setHasScrolledToBottom(true), []);

    const completeBlocked = isAutoAcceptMode && !hasScrolledToBottom;
    const completeTooltip = store.pendingCount > 0
        ? "You must resolve all AI suggestions before completing."
        : completeBlocked
            ? "Scroll to the bottom of the document to complete review."
            : "";

    return (
        <Box sx={{ display: 'flex', height: 'calc(100vh - 32px)' }}>
            <Container maxWidth={false} sx={{ my: 0, display: 'flex', flexDirection: 'column', flexGrow: 1, overflowY: 'auto' }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, pb: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <Box>
                        <Button component={NextLink} href={`/cases/${currentDocument.case || currentDocument.id}`} variant="contained" color="primary">
                            Back to Case
                        </Button>
                    </Box>
                    <Box>
                        <Typography variant="body1" component="h1">{currentDocument?.filename}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                        <Tooltip title="Decrease font size">
                            <span>
                                <IconButton
                                    aria-label="Decrease font size"
                                    onClick={layout.onFontDecrease}
                                    disabled={!layout.canDecreaseFont}
                                    size="small"
                                    sx={{ fontSize: '0.85rem', fontWeight: 'bold' }}
                                >
                                    <TextDecreaseIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Increase font size">
                            <span>
                                <IconButton
                                    aria-label="Increase font size"
                                    onClick={layout.onFontIncrease}
                                    disabled={!layout.canIncreaseFont}
                                    size="small"
                                    sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}
                                >
                                    <TextIncreaseIcon />
                                </IconButton>
                            </span>
                        </Tooltip>
                        {currentDocument.status !== 'Completed' ? (
                            <>
                                <Tooltip title="Resubmit for processing">
                                    <IconButton
                                        aria-label="Resubmit for processing"
                                        color="warning"
                                        onClick={() => docState.setResubmitDialogOpen(true)}
                                        disabled={docState.isResubmitting}
                                    >
                                        <RefreshIcon />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title={completeTooltip}>
                                    <span>
                                        <Button
                                            variant="contained"
                                            color="info"
                                            disabled={store.pendingCount > 0 || completeBlocked || docState.isLoading}
                                            onClick={docState.onMarkAsComplete}
                                            sx={{ minWidth: 180 }}
                                        >
                                            {docState.isLoading ? <CircularProgress size={24} color="inherit" /> : 'Mark as Complete'}
                                        </Button>
                                    </span>
                                </Tooltip>
                            </>
                        ) : (
                            <Button
                                variant="contained"
                                color="success"
                                sx={{ minWidth: 180 }}
                            >
                                Ready for Disclosure
                            </Button>
                        )}
                    </Box>
                </Box>
                {isAutoAcceptMode && (
                    <Alert severity="info" sx={{ mb: 2 }}>
                        All redactions have been pre-accepted. Review and reject any that should not apply.
                        To propagate data subject information across all documents in this case, change a redaction&apos;s type to <strong>DS Info</strong>.
                    </Alert>
                )}
                <DocumentViewer
                    {...getDocumentViewerProps(store, currentDocument)}
                    onScrolledToBottom={isAutoAcceptMode ? handleScrolledToBottom : null}
                />
            </Container>

            <Box
                data-testid="resize-handle"
                onMouseDown={layout.onResizeStart}
                sx={{
                    width: '6px',
                    cursor: 'col-resize',
                    backgroundColor: 'divider',
                    '&:hover': { backgroundColor: 'primary.main' },
                    flexShrink: 0,
                }}
            />
            <Box sx={{ width: layout.sidebarWidth, flexShrink: 0 }}>
                <RedactionSidebar {...getRedactionSidebarProps(store, {
                    exemptionTemplates,
                    documentCompleted: currentDocument.status === 'Completed' && !currentDocument.active_review,
                })} />
            </Box>

            <ManualRedactionPopover
                anchorEl={store.manual.anchor}
                onClose={store.manual.onClose}
                onRedact={store.manual.onCreate}
            />

            {rejectionDialog.target && (
                <RejectReasonDialog
                    open={rejectionDialog.open}
                    onClose={rejectionDialog.onClose}
                    onSubmit={rejectionDialog.onSubmit}
                    redaction={rejectionDialog.target}
                />
            )}

            {markAllInCase.target?.action === 'accept' && (
                <Dialog open onClose={() => markAllInCase.setTarget(null)}>
                    <DialogTitle>Accept all in case</DialogTitle>
                    <DialogContent>
                        <DialogContentText>
                            Accept all pending <strong>{REDACTION_TYPE_LABELS[markAllInCase.target.redactionType] || markAllInCase.target.redactionType}</strong> redactions
                            for <em>&ldquo;{markAllInCase.target.text}&rdquo;</em> across every document in this case?
                        </DialogContentText>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => markAllInCase.setTarget(null)}>Cancel</Button>
                        <Button variant="contained" color="success" onClick={markAllInCase.onAcceptConfirm}>Accept all</Button>
                    </DialogActions>
                </Dialog>
            )}

            <ResubmitDialog
                open={docState.resubmitDialogOpen}
                onClose={() => docState.setResubmitDialogOpen(false)}
                onConfirm={docState.onResubmit}
                isConfirming={docState.isResubmitting}
            />

            <PropagationConfirmDialog
                open={store.propagation.open}
                preview={store.propagation.preview}
                loading={store.propagation.applying}
                onConfirm={store.propagation.onConfirm}
                onCancel={store.propagation.onCancel}
            />
        </Box>
    );
}
