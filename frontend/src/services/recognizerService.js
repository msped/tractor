import apiClient from '@/api/apiClient';
import { extractApiError } from '@/api/apiError';

const BASE = 'model-management/custom-recognizers';

export const getCustomRecognizers = async () => {
    try {
        const response = await apiClient.get(BASE);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to load custom recognizers. Please try again.'));
    }
};

export const createCustomRecognizer = async (data) => {
    try {
        const response = await apiClient.post(BASE, data);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to create recognizer. Please try again.'));
    }
};

export const updateCustomRecognizer = async (id, data) => {
    try {
        const response = await apiClient.patch(`${BASE}/${id}`, data);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to update recognizer. Please try again.'));
    }
};

export const deleteCustomRecognizer = async (id) => {
    try {
        await apiClient.delete(`${BASE}/${id}`);
        return true;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to delete recognizer. Please try again.'));
    }
};

export const validateRegex = async (pattern, sampleText) => {
    try {
        const response = await apiClient.post(
            'model-management/regex/validate',
            { pattern, sample_text: sampleText },
        );
        return response.data;
    } catch (error) {
        if (error.response?.data) {
            return { valid: false, error: error.response.data.error || 'Invalid pattern' };
        }
        throw new Error('Failed to validate regex. Please try again.');
    }
};
