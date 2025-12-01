"use client"

import React, { useState, useEffect, useCallback } from 'react';
import { Typography } from "@mui/material";
import { TrainingUpload } from "@/components/TrainingUpload";
import { TrainingDocList } from "@/components/TrainingDocList";
import { getTrainingDocs } from '@/services/trainingService';
import { useSession } from 'next-auth/react';
import toast from 'react-hot-toast';

export default function TrainingPage() {
    const { data: session } = useSession();
    const [docs, setDocs] = useState([]);

    const fetchDocs = useCallback(async () => {
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
        <>
            <Typography variant="h4" fontWeight={600} component='h1' align={'center'} gutterBottom>
                Manual Training
            </Typography>
            <TrainingUpload onUpload={fetchDocs} unprocessedDocsCount={unprocessedDocsCount} />
            <TrainingDocList docs={docs} refreshDocs={fetchDocs} />
        </>
    );
}
