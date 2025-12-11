"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
    Container,
    Typography,
    TextField,
    Button,
    Box,
    Paper,
    Alert
} from '@mui/material';
import { createCase } from '@/services/caseService';
import { useSession } from "next-auth/react"

export default function NewCasePage() {
    const { data: session } = useSession();

    const router = useRouter();
    const [caseReference, setCaseReference] = useState('');
    const [dataSubjectName, setDataSubjectName] = useState('');
    const [dataSubjectDob, setDataSubjectDob] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState(null);

    const handleSubmit = async (event) => {
        event.preventDefault();
        setIsSubmitting(true);
        setError(null);

        const caseData = {
            case_reference: caseReference,
            data_subject_name: dataSubjectName,
            data_subject_dob: dataSubjectDob || null,
        };

        try {
            const newCase = await createCase(caseData, session.access_token);
            // Redirect to the new case's detail page on success
            router.push(`/cases/${newCase.id}`);
        } catch (e) {
            setError(e.message);
            setIsSubmitting(false);
        }
    };

    return (
        <Container maxWidth="md">
            <Paper sx={{ p: 4, mt: 4 }}>
                <Typography variant="h4" component="h1" fontWeight={600} gutterBottom align="center">
                    Create New Case
                </Typography>
                <Box component="form" onSubmit={handleSubmit} noValidate sx={{ mt: 1 }}>
                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
                    )}
                    <TextField
                        margin="normal"
                        required
                        fullWidth
                        id="case_reference"
                        label="Case Reference"
                        name="case_reference"
                        autoFocus
                        value={caseReference}
                        onChange={(e) => setCaseReference(e.target.value)}
                        disabled={isSubmitting}
                    />
                    <TextField
                        margin="normal"
                        required
                        fullWidth
                        id="data_subject_name"
                        label="Data Subject Name"
                        name="data_subject_name"
                        autoComplete="name"
                        value={dataSubjectName}
                        onChange={(e) => setDataSubjectName(e.target.value)}
                        disabled={isSubmitting}
                    />
                    <TextField
                        margin="normal"
                        fullWidth
                        id="data_subject_dob"
                        label="Data Subject Date of Birth"
                        name="data_subject_dob"
                        type="date"
                        slotProps={{
                            inputLabel: {
                                shrink: true,
                            }
                        }}
                        value={dataSubjectDob}
                        onChange={(e) => setDataSubjectDob(e.target.value)}
                        disabled={isSubmitting}
                    />
                    <Button
                        type="submit"
                        fullWidth
                        variant="contained"
                        sx={{ mt: 3, mb: 2 }}
                        disabled={isSubmitting}
                    >
                        {isSubmitting ? 'Creating...' : 'Create Case'}
                    </Button>
                </Box>
            </Paper>
        </Container>
    );
}
