import apiClient from '@/api/apiClient';
import { extractApiError } from '@/api/apiError';

export const createCase = async (caseData) => {
    try {
        const response = await apiClient.post(`/cases`, caseData);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to create case. Please try again.'));
    }
};

export const getCase = async (caseId) => {
    try {
        const response = await apiClient.get(`/cases/${caseId}`);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to get case. Please try again.'));
    }
};

export const updateCase = async (caseId, updateData) => {
    try {
        const response = await apiClient.patch(`/cases/${caseId}`, updateData);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to update case. Please try again.'));
    }
};

export const deleteCase = async (caseId) => {
    try {
        const response = await apiClient.delete(`/cases/${caseId}`);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to delete case. Please try again.'));
    }
};

export const getCases = async () => {
    try {
        const response = await apiClient.get('/cases');
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to retrieve cases. Please try again.'));
    }
};

export const getExportSettings = async () => {
    try {
        const response = await apiClient.get('/cases/settings/export');
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to get export settings. Please try again.'));
    }
};

export const updateExportSettings = async (data) => {
    try {
        const response = await apiClient.patch('/cases/settings/export', data);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to update export settings. Please try again.'));
    }
};

export const createCaseExport = async (caseId) => {
    try {
        const response = await apiClient.post(`/cases/${caseId}/export`, {});
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to create export. Please try again.'));
    }
};
