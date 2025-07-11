"use server"

import apiClient from '@/api/apiClient';
import { auth } from '@/auth';

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
        console.log("Redaction updated successfully:", response.data);
        return response.data
    } catch (error) {
        console.error("Error updating redaction:", error);
    }
};

export const deleteManualRedaction = async (redactionId) => {
    const session = await auth();
    return apiClient.delete(
        `cases/document/redaction/${redactionId}`,
        {
            headers: {
                'Authorization': `Bearer ${session.access_token}`,
            },
        }
    );
};