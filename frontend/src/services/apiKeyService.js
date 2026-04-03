import apiClient from '@/api/apiClient';

export const getApiKeys = async (accessToken) => {
    try {
        const response = await apiClient.get('/auth/api-keys', {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to get API keys:", error.response?.data || error.message);
        throw new Error("Failed to load API keys. Please try again.");
    }
};

export const createApiKey = async (description, accessToken) => {
    try {
        const response = await apiClient.post(
            '/auth/api-keys',
            { description },
            {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            }
        );
        return response.data;
    } catch (error) {
        console.error("Failed to create API key:", error.response?.data || error.message);
        throw new Error("Failed to create API key. Please try again.");
    }
};

export const revokeApiKey = async (keyId, accessToken) => {
    try {
        await apiClient.delete(`/auth/api-keys/${keyId}`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return true;
    } catch (error) {
        console.error("Failed to revoke API key:", error.response?.data || error.message);
        throw new Error("Failed to revoke API key. Please try again.");
    }
};
