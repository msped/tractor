import apiClient from '@/api/apiClient';
import { throwApiError } from '@/api/apiError';

export const getApiKeys = async () => {
    try {
        const response = await apiClient.get('/auth/api-keys');
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to load API keys. Please try again.');
    }
};

export const createApiKey = async (description, expiresAt = null) => {
    try {
        const body = { description };
        if (expiresAt) body.expires_at = expiresAt;
        const response = await apiClient.post('/auth/api-keys', body);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to create API key. Please try again.');
    }
};

export const revokeApiKey = async (keyId) => {
    try {
        await apiClient.delete(`/auth/api-keys/${keyId}`);
        return true;
    } catch (error) {
        throwApiError(error, 'Failed to revoke API key. Please try again.');
    }
};
