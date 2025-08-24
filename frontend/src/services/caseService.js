"use server"

import apiClient from '@/api/apiClient';
import { auth } from '@/auth';
import { revalidatePath } from 'next/cache';

export const createCase = async (caseData) => {
    const session = await auth();
    try {
        const response = await apiClient.post(`/cases`, caseData, {
            headers: {
                'Authorization': `Bearer ${session.access_token}`,
            },
        });
        // Revalidate the cases list page to show the new case
        revalidatePath('/cases');
        return response.data;
    } catch (error) {
        console.error("Failed to create case:", error.response?.data || error.message);
        throw new Error("Failed to create case. Please try again.");
    }
};
