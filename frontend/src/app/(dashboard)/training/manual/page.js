"use client"

import React, { useState, useEffect, useCallback } from 'react';
import { Container } from "@mui/material";
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
        </Container>
    );
}
