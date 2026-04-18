"use client"

import React, { useState, useEffect, useCallback } from 'react';
import { Container, Typography, Card, CardContent } from "@mui/material";
import { TrainingUpload } from "@/components/TrainingUpload";
import { TrainingDocList } from "@/components/TrainingDocList";
import { getTrainingDocs } from '@/services/trainingService';
import { useSession } from 'next-auth/react';
import toast from 'react-hot-toast';

export default function TrainingPage() {
    const { data: session } = useSession();
    const [docs, setDocs] = useState([]);

    const fetchDocs = useCallback(async () => {
        if (!session?.access_token) return;
        try {
            const data = await getTrainingDocs(session?.access_token);
            setDocs(data);
        } catch (error) {
            toast.error(error.message);
        }
    }, [session?.access_token]);

    useEffect(() => {
        fetchDocs();
    }, [fetchDocs]);

    const unprocessedDocsCount = docs.filter(d => !d.processed).length;

    return (
        <Container>
            <TrainingUpload onUpload={fetchDocs} unprocessedDocsCount={unprocessedDocsCount} />
            <TrainingDocList docs={docs} refreshDocs={fetchDocs} />
            <Card sx={{ mt: 4 }}>
                <CardContent>
                    <Typography variant="h5" component="h3">
                        How to provide manual training data
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        To provide manual training data, navigate to the Manual Training section
                        where you can upload documents labelled documents.
                        This helps improve the models accuracy in detecting and redacting
                        data.
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                        The only supported files for training are docx files. The document must
                        be highlighted using turquoise for operation data and bright green
                        for Third Party information.
                    </Typography>
                </CardContent>
            </Card>
        </Container>
    );
}
