"use server"

import apiClient from '@/api/apiClient';
import { auth } from '@/auth';

export const getDocument = async (docId) => {
    const session = await auth();
    try {
        const response = await apiClient.get(`/cases/documents/${docId}`, {
            headers: {
                'Authorization': `Bearer ${session.access_token}`,
            },
        });
        return response.data;
    } catch (error) {
        throw error;
    }
};