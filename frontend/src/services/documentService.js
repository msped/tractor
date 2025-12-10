import apiClient from '@/api/apiClient';

export const getDocument = async (docId, accessToken) => {

    try {
        const response = await apiClient.get(`/cases/documents/${docId}`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to retrieve document: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to retrieve document. Please try again.');
        }
    }
};

export const uploadDocuments = async (caseId, formData, accessToken) => {
    try {
        const response = await apiClient.post(`/cases/${caseId}/documents`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to upload document(s): ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to upload document(s). Please try again.');
        }
    }
}

export const deleteDocument = async (docId, accessToken) => {
    try {
        const response = await apiClient.delete(`/cases/documents/${docId}`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.status === 204;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to delete document: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to delete document. Please try again.');
        }
    }
}

export const markAsComplete = async (docId, accessToken) => {

    try {
        const response = await apiClient.patch(`cases/documents/${docId}`, {
            new_status: 'COMPLETED'
        }, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to mark document as complete: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to mark document as complete. Please try again.');
        }
    }
}