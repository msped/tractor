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
        if (error.response && error.response.data) {
            throw new Error(`Failed to create redaction: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to create redaction. Please try again.');
        }
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
        if (error.response && error.response.data) {
            throw new Error(`Failed to create redaction: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to create redaction. Please try again.');
        }
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
        if (error.response && error.response.data) {
            throw new Error(`Failed to create redaction: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to create redaction. Please try again.');
        }
    }
};

export const updateRedactionContext = async (redactionId, contextData) => {
    const session = await auth();

    try {
        const response = await apiClient.post(
            `cases/document/redaction/${redactionId}/context`,
            contextData,
            {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            }
        );
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to update redaction context: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to update redaction context. Please try again.');
        }
    }
};

export const deleteRedactionContent = async (redactionId) => {
    const session = await auth();

    try {
        const response = await apiClient.delete(
            `cases/document/redaction/${redactionId}/context`,
            {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            }
        );
        return response.status === 204;

    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to delete redaction context: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to delete redaction context. Please try again.');
        }
    }
};