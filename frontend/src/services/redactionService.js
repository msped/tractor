"use server"

import apiClient from '@/api/apiClient';
import { auth } from '@/auth';

export const createRedaction = async (documentId, createData) => {
    const session = await auth();

    try {
        const response = await apiClient.post(
            `cases/document/${documentId}/redaction`,
            createData,
            {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            }
        );
        return response.data
    } catch (error) {
        console.error("Error updating redaction:", error.response?.data || error);
    }
};

export const updateRedaction = async (redactionId, updateData) => {
    const session = await auth();

    try {
        const response = await apiClient.patch(
            `cases/document/redaction/${redactionId}`,
            updateData,
            {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            }
        );
        return response.data
    } catch (error) {
        console.error("Error updating redaction:", error);
    }
};

export const deleteRedaction = async (redactionId) => {
    const session = await auth();

    try {
        const response = await apiClient.delete(
            `cases/document/redaction/${redactionId}`,
            {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            }
        );
        return response.status === 204;

    } catch (error) {
        console.error("Error deleting redaction:", error.response?.data || error);
    }
};