import apiClient from '@/api/apiClient';

export const getDocument = async (docId) => {
    try {
        const response = await apiClient.get(`/cases/documents/${docId}`);
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to retrieve document: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to retrieve document. Please try again.');
        }
    }
};

export const getDocumentForReview = async (caseId, docId) => {
    try {
        const response = await apiClient.get(`/cases/${caseId}/document/${docId}/review`);
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to retrieve document for review: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to retrieve document for review. Please try again.');
        }
    }
};

export const resubmitDocument = async (docId) => {
    try {
        const response = await apiClient.post(`/cases/documents/${docId}/resubmit`, {});
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to upload document(s): ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to upload document(s). Please try again.');
        }
    }
}

export const cancelProcessing = async (docId) => {
    try {
        const response = await apiClient.post(`/cases/documents/${docId}/cancel`, {});
        return response.data;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to cancel processing: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to cancel processing. Please try again.');
        }
    }
}

export const uploadDocuments = async (caseId, formData) => {
    try {
        const response = await apiClient.post(`/cases/${caseId}/documents`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
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

export const deleteDocument = async (docId) => {
    try {
        const response = await apiClient.delete(`/cases/documents/${docId}`);
        return response.status === 204;
    } catch (error) {
        if (error.response && error.response.data) {
            throw new Error(`Failed to delete document: ${error.response.data.detail || 'Unknown error'}`);
        } else {
            throw new Error('Failed to delete document. Please try again.');
        }
    }
}

export const markAsComplete = async (docId) => {
    try {
        const response = await apiClient.patch(`cases/documents/${docId}`, {
            new_status: 'COMPLETED'
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
