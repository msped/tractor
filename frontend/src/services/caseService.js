import apiClient from '@/api/apiClient';

export const createCase = async (caseData, accessToken) => {
    try {
        const response = await apiClient.post(`/cases`, caseData, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to create case:", error.response?.data || error.message);
        throw new Error("Failed to create case. Please try again.");
    }
};

export const getCase = async (caseId, accessToken) => {

    try {
        const response = await apiClient.get(`/cases/${caseId}`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to get case:", error.response?.data || error.message);
        throw new Error("Failed to get case. Please try again.");
    }
};

export const updateCase = async (caseId, updateData, accessToken) => {
    try {
        const response = await apiClient.patch(`/cases/${caseId}`, updateData, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to update case:", error.response?.data || error.message);
        throw new Error("Failed to update case. Please try again.");
    }
}

export const deleteCase = async (caseId, accessToken) => {
    try {
        const response = await apiClient.delete(`/cases/${caseId}`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to delete case:", error.response?.data || error.message);
        throw new Error("Failed to delete case. Please try again.");
    }
}

export const createCaseExport = async (caseId, accessToken) => {
    try {
        const response = await apiClient.post(`/cases/${caseId}/export`, {}, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        console.error("Failed to create export:", error.response?.data || error.message);
        throw new Error("Failed to create export. Please try again.");
    }
};