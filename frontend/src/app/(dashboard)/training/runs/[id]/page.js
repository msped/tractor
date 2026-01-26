import Link from "next/link";
import {
    Typography,
    Paper,
    Box,
    Container,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Chip,
} from "@mui/material";
import { getTrainingRunDetail } from '@/services/trainingService';
import { auth } from "@/auth";
import { DownloadTrainingDocButton } from "@/components/DownloadTrainingDocButton";

function formatScore(score) {
    return score ? (score * 100).toFixed(2) + '%' : 'N/A';
}

function formatSource(source) {
    const sourceMap = {
        'training_docs': 'Training Documents',
        'redactions': 'Case Redactions',
        'both': 'Both Sources'
    };
    return sourceMap[source] || String(source || 'Unknown');
}

export default async function TrainingRunDetailPage({ params }) {
    const { id } = await params;
    const session = await auth();
    let run = null, error = null;

    try {
        run = await getTrainingRunDetail(id, session?.access_token);
    } catch (e) {
        error = e.message;
    }

    if (error || !run) {
        return (
            <Container>
                <Typography color="error">{error || "Training run not found"}</Typography>
            </Container>
        );
    }

    const sourceLabel = formatSource(run.source);

    return (
        <Container sx={{ mt: 2 }}>
            <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" sx={{ mb: 2 }}>Training Run Details</Typography>

                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2, mb: 3 }}>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Model Name</Typography>
                        <Typography sx={{ fontFamily: 'monospace' }}>{run.model_name}</Typography>
                    </Box>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Date</Typography>
                        <Typography>{new Date(run.created_at).toLocaleString('en-GB')}</Typography>
                    </Box>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Source</Typography>
                        <Box>
                            <Chip label={sourceLabel} size="small" />
                        </Box>
                    </Box>
                </Box>

                <Typography variant="h6" sx={{ mb: 1 }}>Performance Scores</Typography>
                <Box sx={{ display: 'flex', gap: 3 }}>
                    <Box>
                        <Typography variant="caption" color="text.secondary">F1-Score</Typography>
                        <Typography variant="h6">{formatScore(run.f1_score)}</Typography>
                    </Box>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Precision</Typography>
                        <Typography variant="h6">{formatScore(run.precision)}</Typography>
                    </Box>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Recall</Typography>
                        <Typography variant="h6">{formatScore(run.recall)}</Typography>
                    </Box>
                </Box>
            </Paper>

            {run.training_documents && run.training_documents.length > 0 && (
                <Paper sx={{ p: 3, mb: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2 }}>Training Documents</Typography>
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Document Name</TableCell>
                                    <TableCell>Created At</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {run.training_documents.map((doc) => (
                                    <TableRow key={doc.id}>
                                        <TableCell>{doc.name}</TableCell>
                                        <TableCell>{new Date(doc.created_at).toLocaleString('en-GB')}</TableCell>
                                        <TableCell align="right">
                                            <DownloadTrainingDocButton fileUrl={doc.original_file} filename={doc.name} />
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}

            {run.case_documents && run.case_documents.length > 0 && (
                <Paper sx={{ p: 3, mb: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2 }}>Case Documents Used</Typography>
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Document Name</TableCell>
                                    <TableCell>Case</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {run.case_documents.map((doc) => (
                                    <TableRow key={doc.id}>
                                        <TableCell>{doc.filename}</TableCell>
                                        <TableCell>
                                            <Link href={`/cases/${doc.case_id}`} style={{ textDecoration: 'none' }}>
                                                View Case
                                            </Link>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}

            {(!run.training_documents || run.training_documents.length === 0) &&
             (!run.case_documents || run.case_documents.length === 0) && (
                <Paper sx={{ p: 3 }}>
                    <Typography color="text.secondary">
                        No documents recorded for this training run.
                    </Typography>
                </Paper>
            )}
        </Container>
    );
}
