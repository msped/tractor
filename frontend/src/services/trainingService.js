"use server"

import apiClient from '@/api/apiClient';
import { auth } from '@/auth';

export const getModels = async () => {
    const session = await auth();
    if (!session) throw new Error("Not authenticated");

    try {
        const response = await apiClient.get(`/models`, {
            headers: {
                'Authorization': `Bearer ${session.access_token}`,
            },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to fetch models:", error.response?.data || error.message);
        throw new Error("Failed to fetch models. You may not have permission to view this page.");
    }
};

export const setActiveModel = async (modelId) => {
    const session = await auth();
    if (!session) throw new Error("Not authenticated");

    try {
        await apiClient.post(`/models/${modelId}/set-active`, {}, {
            headers: { 'Authorization': `Bearer ${session.access_token}` },
        });
    } catch (error) {
        console.error("Failed to set active model:", error.response?.data || error.message);
        throw new Error("Failed to set active model.");
    }
};

