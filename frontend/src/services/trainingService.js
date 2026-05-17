import apiClient from '@/api/apiClient';
import { extractApiError } from '@/api/apiError';

export const getModels = async () => {
    try {
        const response = await apiClient.get(`/models`);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to fetch models. Please try again.'));
    }
};

export const setActiveModel = async (modelId) => {
    try {
        await apiClient.post(`/models/${modelId}/set-active`, {});
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to set active model. Please try again.'));
    }
};

export const deleteModel = async (modelId) => {
    try {
        await apiClient.delete(`/models/${modelId}`);
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to delete model. Please try again.'));
    }
};

export const getTrainingDocs = async () => {
    try {
        const response = await apiClient.get(`/training-docs`);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to fetch training documents. Please try again.'));
    }
};

export const getTrainingSchedules = async () => {
    try {
        const response = await apiClient.get(`/schedules`);
        return response.data.length > 0 ? response.data[0] : null;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to fetch training schedules. Please try again.'));
    }
};

export const createTrainingSchedule = async (scheduleData) => {
    try {
        const response = await apiClient.post(`/schedules`, scheduleData);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to create training schedule. Please try again.'));
    }
};

export const deleteTrainingSchedule = async (scheduleId) => {
    try {
        await apiClient.delete(`/schedules/${scheduleId}`);
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to delete training schedule. Please try again.'));
    }
};

export const getTrainingRuns = async () => {
    try {
        const response = await apiClient.get(`/training-runs`);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to fetch training runs. Please try again.'));
    }
};

export const getTrainingRunDetail = async (id) => {
    try {
        const response = await apiClient.get(`/training-runs/${id}`);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to fetch training run details. Please try again.'));
    }
};

export const deleteTrainingDoc = async (docId) => {
    try {
        await apiClient.delete(`/training-docs/${docId}`);
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to delete document. Please try again.'));
    }
};

export const uploadTrainingDoc = async (file) => {
    const formData = new FormData();
    formData.append('original_file', file);
    formData.append('name', file.name);

    try {
        await apiClient.post(`/training-docs`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to upload document. Please try again.'));
    }
};

export const getTrainingStatus = async () => {
    try {
        const response = await apiClient.get(`/model-management/status`);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to fetch training status. Please try again.'));
    }
};

export const getLLMPromptSettings = async () => {
    try {
        const response = await apiClient.get(`/llm-prompt-settings`);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to fetch LLM prompt settings. Please try again.'));
    }
};

export const updateLLMPromptSettings = async (data) => {
    try {
        const response = await apiClient.patch(`/llm-prompt-settings`, data);
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to update LLM prompt settings. Please try again.'));
    }
};

export const runManualTraining = async () => {
    try {
        const response = await apiClient.post(`/model-management/run-now`, {});
        return response.data;
    } catch (error) {
        throw new Error(extractApiError(error, 'Failed to start training process. Please try again.'));
    }
};
