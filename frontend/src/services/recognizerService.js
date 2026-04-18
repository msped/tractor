import apiClient from '@/api/apiClient';

const BASE = 'model-management/custom-recognizers';

const headers = (token) => ({ Authorization: `Bearer ${token}` });

export const getCustomRecognizers = async (accessToken) => {
    try {
        const response = await apiClient.get(BASE, { headers: headers(accessToken) });
        return response.data;
    } catch (error) {
        throw new Error('Failed to load custom recognizers.');
    }
};

export const createCustomRecognizer = async (data, accessToken) => {
    try {
        const response = await apiClient.post(BASE, data, { headers: headers(accessToken) });
        return response.data;
    } catch (error) {
        const detail = error.response?.data?.name?.[0]
            || error.response?.data?.non_field_errors?.[0]
            || error.response?.data?.detail
            || 'Unknown error';
        throw new Error(`Failed to create recognizer: ${detail}`);
    }
};

export const updateCustomRecognizer = async (id, data, accessToken) => {
    try {
        const response = await apiClient.patch(`${BASE}/${id}`, data, { headers: headers(accessToken) });
        return response.data;
    } catch (error) {
        const detail = error.response?.data?.non_field_errors?.[0]
            || error.response?.data?.detail
            || 'Unknown error';
        throw new Error(`Failed to update recognizer: ${detail}`);
    }
};

export const deleteCustomRecognizer = async (id, accessToken) => {
    try {
        await apiClient.delete(`${BASE}/${id}`, { headers: headers(accessToken) });
        return true;
    } catch (error) {
        throw new Error('Failed to delete recognizer.');
    }
};

export const validateRegex = async (pattern, sampleText, accessToken) => {
    try {
        const response = await apiClient.post(
            'model-management/regex/validate',
            { pattern, sample_text: sampleText },
            { headers: headers(accessToken) }
        );
        return response.data;
    } catch (error) {
        if (error.response?.data) {
            return { valid: false, error: error.response.data.error || 'Invalid pattern' };
        }
        throw new Error('Failed to validate regex.');
    }
};
