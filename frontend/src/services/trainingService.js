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

export const getTrainingDocs = async () => {
    const session = await auth();
    if (!session) throw new Error("Not authenticated");

    try {
        const response = await apiClient.get(`/training-docs`, {
            headers: { 'Authorization': `Bearer ${session.access_token}` },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to fetch training docs:", error.response?.data || error.message);
        throw new Error("Failed to fetch training documents.");
    }
};

export const getTrainingSchedules = async () => {
    const session = await auth();
    if (!session) throw new Error("Not authenticated");

    try {
        const response = await apiClient.get(`/schedules`, {
            headers: { 'Authorization': `Bearer ${session.access_token}` },
        });
        // Assuming there is only one schedule as per the request
        return response.data.length > 0 ? response.data[0] : null;
    } catch (error) {
        console.error("Failed to fetch training schedules:", error.response?.data || error.message);
        throw new Error("Failed to fetch training schedules.");
    }
};

export const getTrainingRuns = async () => {
    const session = await auth();
    if (!session) throw new Error("Not authenticated");

    try {
        const response = await apiClient.get(`/training-runs`, {
            headers: { 'Authorization': `Bearer ${session.access_token}` },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to fetch training runs:", error.response?.data || error.message);
        throw new Error("Failed to fetch training runs.");
    }
};

export const deleteTrainingDoc = async (docId) => {
    const session = await auth();
    if (!session) throw new Error("Not authenticated");

    try {
        await apiClient.delete(`/training-docs/${docId}`, {
            headers: { 'Authorization': `Bearer ${session.access_token}` },
        });
    } catch (error) {
        console.error("Failed to delete training doc:", error.response?.data || error.message);
        const errorMessage = error.response?.data?.detail || "Failed to delete document.";
        throw new Error(errorMessage);
    }
};

export const uploadTrainingDoc = async (file) => {
    const session = await auth();
    if (!session) throw new Error("Not authenticated");

    const formData = new FormData();
    formData.append('original_file', file);
    formData.append('name', file.name);

    try {
        await apiClient.post(`/training-docs`, formData, {
            headers: {
                'Authorization': `Bearer ${session.access_token}`,
                'Content-Type': 'multipart/form-data',
            },
        });
    } catch (error) {
        console.error("Failed to upload training doc:", error.response?.data || error.message);
        const errorMessage = error.response?.data?.detail || "Failed to upload document.";
        throw new Error(errorMessage);
    }
};

export const runManualTraining = async () => {
    const session = await auth();
    if (!session) throw new Error("Not authenticated");

    try {
        const response = await apiClient.post(`/training/run-now`, {}, {
            headers: { 'Authorization': `Bearer ${session.access_token}` },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to start training:", error.response?.data || error.message);
        const errorMessage = error.response?.data?.detail || "Failed to start training process.";
        throw new Error(errorMessage);
    }
};
