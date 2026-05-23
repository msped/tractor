import apiClient from '@/api/apiClient';
import { throwApiError } from '@/api/apiError';

export const createRedaction = async (documentId, createData) => {
    try {
        const response = await apiClient.post(
            `cases/document/${documentId}/redaction`,
            createData,
        );
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to create redaction. Please try again.');
    }
};

export const updateRedaction = async (redactionId, updateData) => {
    try {
        const response = await apiClient.patch(
            `cases/document/redaction/${redactionId}`,
            updateData,
        );
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to update redaction. Please try again.');
    }
};

export const deleteRedaction = async (redactionId) => {
    try {
        const response = await apiClient.delete(
            `cases/document/redaction/${redactionId}`,
        );
        return response.status === 204;
    } catch (error) {
        throwApiError(error, 'Failed to delete redaction. Please try again.');
    }
};

export const bulkMarkByText = async (caseId, text, redactionType, markStatus, rejectionReason) => {
    try {
        const body = { text, redaction_type: redactionType, status: markStatus };
        if (rejectionReason) body.rejection_reason = rejectionReason;
        const response = await apiClient.post(
            `cases/${caseId}/redactions/bulk-by-text/`,
            body,
        );
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to bulk mark redactions. Please try again.');
    }
};

export const bulkUpdateRedactions = async (documentId, ids, isAccepted, justification) => {
    try {
        const response = await apiClient.patch(
            `cases/document/${documentId}/redactions/bulk/`,
            { ids, is_accepted: isAccepted, justification: justification ?? null },
        );
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to bulk update redactions. Please try again.');
    }
};

export const updateRedactionContext = async (redactionId, contextData) => {
    try {
        const response = await apiClient.post(
            `cases/document/redaction/${redactionId}/context`,
            contextData,
        );
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to update redaction context. Please try again.');
    }
};

export const getExemptionTemplates = async () => {
    try {
        const response = await apiClient.get('cases/exemptions');
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to load exemption templates. Please try again.');
    }
};

export const createExemptionTemplate = async (data) => {
    try {
        const response = await apiClient.post('cases/exemptions', data);
        return response.data;
    } catch (error) {
        throwApiError(error, 'Failed to create exemption template. Please try again.');
    }
};

export const deleteExemptionTemplate = async (templateId) => {
    try {
        await apiClient.delete(`cases/exemptions/${templateId}`);
        return true;
    } catch (error) {
        throwApiError(error, 'Failed to delete exemption template. Please try again.');
    }
};

export const deleteRedactionContext = async (redactionId) => {
    try {
        const response = await apiClient.delete(
            `cases/document/redaction/${redactionId}/context`,
        );
        return response.status === 204;
    } catch (error) {
        throwApiError(error, 'Failed to delete redaction context. Please try again.');
    }
};
