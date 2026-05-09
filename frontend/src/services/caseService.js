import apiClient from '@/api/apiClient';

export const createCase = async (caseData) => {
    try {
        const response = await apiClient.post(`/cases`, caseData);
        return response.data;
    } catch (error) {
        console.error("Failed to create case:", error.response?.data || error.message);
        throw new Error("Failed to create case. Please try again.");
    }
};

export const getCase = async (caseId) => {
    try {
        const response = await apiClient.get(`/cases/${caseId}`);
        return response.data;
    } catch (error) {
        console.error("Failed to get case:", error.response?.data || error.message);
        throw new Error("Failed to get case. Please try again.");
    }
};

export const updateCase = async (caseId, updateData) => {
    try {
        const response = await apiClient.patch(`/cases/${caseId}`, updateData);
        return response.data;
    } catch (error) {
        console.error("Failed to update case:", error.response?.data || error.message);
        throw new Error("Failed to update case. Please try again.");
    }
}

export const deleteCase = async (caseId) => {
    try {
        const response = await apiClient.delete(`/cases/${caseId}`);
        return response.data;
    } catch (error) {
        console.error("Failed to delete case:", error.response?.data || error.message);
        throw new Error("Failed to delete case. Please try again.");
    }
}

export const getCases = async () => {
    try {
        const response = await apiClient.get('/cases');
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to retrieve cases: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to retrieve cases. Please try again.');
        }
    }
};

export const getExportSettings = async () => {
    try {
        const response = await apiClient.get('/cases/settings/export');
        return response.data;
    } catch (error) {
        console.error("Failed to get export settings:", error.response?.data || error.message);
        throw new Error("Failed to get export settings. Please try again.");
    }
};

export const updateExportSettings = async (data) => {
    try {
        const response = await apiClient.patch('/cases/settings/export', data);
        return response.data;
    } catch (error) {
        console.error("Failed to update export settings:", error.response?.data || error.message);
        throw new Error("Failed to update export settings. Please try again.");
    }
};

export const createCaseExport = async (caseId) => {
    try {
        const response = await apiClient.post(`/cases/${caseId}/export`, {});
        return response.data;
    } catch (error) {
        console.error("Failed to create export:", error.response?.data || error.message);
        throw new Error("Failed to create export. Please try again.");
    }
};
