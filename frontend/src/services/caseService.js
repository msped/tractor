import apiClient from '@/api/apiClient';
import { throwApiError } from '@/api/apiError';

export const createCase = async (caseData) => {
    try {
        const response = await apiClient.post(`/cases`, caseData);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to create case. Please try again.');
    }
};

export const getCase = async (caseId) => {
    try {
        const response = await apiClient.get(`/cases/${caseId}`);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to get case. Please try again.');
    }
};

export const updateCase = async (caseId, updateData) => {
    try {
        const response = await apiClient.patch(`/cases/${caseId}`, updateData);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to update case. Please try again.');
    }
};

export const deleteCase = async (caseId) => {
    try {
        const response = await apiClient.delete(`/cases/${caseId}`);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to delete case. Please try again.');
    }
};

export const getCases = async (params = {}) => {
    try {
        const response = await apiClient.get('/cases', { params });
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to retrieve cases. Please try again.');
    }
};

export const getExportSettings = async () => {
    try {
        const response = await apiClient.get('/cases/settings/export');
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to get export settings. Please try again.');
    }
};

export const updateExportSettings = async (data) => {
    try {
        const response = await apiClient.patch('/cases/settings/export', data);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to update export settings. Please try again.');
    }
};

export const createCaseExport = async (caseId) => {
    try {
        const response = await apiClient.post(`/cases/${caseId}/export`, {});
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to create export. Please try again.');
    }
};

export const getCaseExports = async (caseId) => {
    try {
        const response = await apiClient.get(`/cases/${caseId}/exports`);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to retrieve export history. Please try again.');
    }
};

export const openCaseReview = async (caseId) => {
    try {
        const response = await apiClient.post(`/cases/${caseId}/reviews`, {});
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to open the review. Please try again.');
    }
};

export const getRetentionSettings = async () => {
    try {
        const response = await apiClient.get('/cases/settings/retention');
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to retrieve retention settings.');
    }
};

export const getReviewWorkflowSettings = async () => {
    try {
        const response = await apiClient.get('/cases/settings/review-workflow');
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to retrieve review workflow settings.');
    }
};

export const updateReviewWorkflowSettings = async (data) => {
    try {
        const response = await apiClient.patch('/cases/settings/review-workflow', data);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to update review workflow settings.');
    }
};

export const bulkDeleteCases = async (ids) => {
    try {
        const response = await apiClient.post('/cases/settings/retention/bulk-delete', { ids });
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to delete cases.');
    }
};
