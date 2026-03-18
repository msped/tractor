import apiClient from '@/api/apiClient';

export const createRedaction = async (documentId, createData, accessToken) => {

    try {
        const response = await apiClient.post(
            `cases/document/${documentId}/redaction`,
            createData,
            {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            }
        );
        return response.data
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to create redaction: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to create redaction. Please try again.');
        }
    }
};

export const updateRedaction = async (redactionId, updateData, accessToken) => {

    try {
        const response = await apiClient.patch(
            `cases/document/redaction/${redactionId}`,
            updateData,
            {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            }
        );
        return response.data
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to create redaction: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to create redaction. Please try again.');
        }
    }
};

export const deleteRedaction = async (redactionId, accessToken) => {

    try {
        const response = await apiClient.delete(
            `cases/document/redaction/${redactionId}`,
            {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            }
        );
        return response.status === 204;

    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to create redaction: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to create redaction. Please try again.');
        }
    }
};

export const bulkUpdateRedactions = async (documentId, ids, isAccepted, justification, accessToken) => {
    try {
        const response = await apiClient.patch(
            `cases/document/${documentId}/redactions/bulk/`,
            { ids, is_accepted: isAccepted, justification: justification ?? null },
            {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            }
        );
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to bulk update redactions: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to bulk update redactions. Please try again.');
        }
    }
};

export const updateRedactionContext = async (redactionId, contextData, accessToken) => {

    try {
        const response = await apiClient.post(
            `cases/document/redaction/${redactionId}/context`,
            contextData,
            {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            }
        );
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to update redaction context: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to update redaction context. Please try again.');
        }
    }
};

export const getExemptionTemplates = async (accessToken) => {
    try {
        const response = await apiClient.get(
            'cases/exemptions',
            { headers: { 'Authorization': `Bearer ${accessToken}` } }
        );
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to load exemption templates: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to load exemption templates. Please try again.');
        }
    }
};

export const createExemptionTemplate = async (data, accessToken) => {
    try {
        const response = await apiClient.post(
            'cases/exemptions',
            data,
            { headers: { 'Authorization': `Bearer ${accessToken}` } }
        );
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            const detail = error.response.data.name?.[0] || error.response.data.detail || 'Unknown error';
            throw new Error(`Failed to create exemption template: ${detail}`);
        } else {
            throw new Error('Failed to create exemption template. Please try again.');
        }
    }
};

export const deleteExemptionTemplate = async (templateId, accessToken) => {
    try {
        await apiClient.delete(
            `cases/exemptions/${templateId}`,
            { headers: { 'Authorization': `Bearer ${accessToken}` } }
        );
        return true;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to delete exemption template: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to delete exemption template. Please try again.');
        }
    }
};

export const deleteRedactionContext = async (redactionId, accessToken) => {

    try {
        const response = await apiClient.delete(
            `cases/document/redaction/${redactionId}/context`,
            {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            }
        );
        return response.status === 204;

    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to delete redaction context: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to delete redaction context. Please try again.');
        }
    }
};