import apiClient from '@/api/apiClient';

const BASE = 'model-management/custom-recognizers';

export const getCustomRecognizers = async () => {
    try {
        const response = await apiClient.get(BASE);
        return response.data;
    } catch (error) {
        throw new Error('Failed to load custom recognizers.');
    }
};

export const createCustomRecognizer = async (data) => {
    try {
        const response = await apiClient.post(BASE, data);
        return response.data;
    } catch (error) {
        const detail = error.response?.data?.name?.[0]
            || error.response?.data?.non_field_errors?.[0]
            || error.response?.data?.detail
            || 'Unknown error';
        throw new Error(`Failed to create recognizer: ${detail}`);
    }
};

export const updateCustomRecognizer = async (id, data) => {
    try {
        const response = await apiClient.patch(`${BASE}/${id}`, data);
        return response.data;
    } catch (error) {
        const detail = error.response?.data?.non_field_errors?.[0]
            || error.response?.data?.detail
            || 'Unknown error';
        throw new Error(`Failed to update recognizer: ${detail}`);
    }
};

export const deleteCustomRecognizer = async (id) => {
    try {
        await apiClient.delete(`${BASE}/${id}`);
        return true;
    } catch (error) {
        throw new Error('Failed to delete recognizer.');
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
        throw new Error('Failed to validate regex.');
    }
};
