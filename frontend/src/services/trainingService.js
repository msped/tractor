import apiClient from '@/api/apiClient';

export const getModels = async () => {
    try {
        const response = await apiClient.get(`/models`);
        return response.data;
    } catch (error) {
        console.error("Failed to fetch models:", error.response?.data || error.message);
        throw new Error("Failed to fetch models. You may not have permission to view this page.");
    }
};

export const setActiveModel = async (modelId) => {
    try {
        await apiClient.post(`/models/${modelId}/set-active`, {});
    } catch (error) {
        console.error("Failed to set active model:", error.response?.data || error.message);
        throw new Error("Failed to set active model.");
    }
};

export const deleteModel = async (modelId) => {
    try {
        await apiClient.delete(`/models/${modelId}`);
    } catch (error) {
        console.error("Failed to delete model:", error.response?.data || error.message);
        const errorMessage = error.response?.data?.detail || "Failed to delete model.";
        throw new Error(errorMessage);
    }
};

export const getTrainingDocs = async () => {
    try {
        const response = await apiClient.get(`/training-docs`);
        return response.data;
    } catch (error) {
        console.error("Failed to fetch training docs:", error.response?.data || error.message);
        throw new Error("Failed to fetch training documents.");
    }
};

export const getTrainingSchedules = async () => {
    try {
        const response = await apiClient.get(`/schedules`);
        return response.data.length > 0 ? response.data[0] : null;
    } catch (error) {
        console.error("Failed to fetch training schedules:", error.response?.data || error.message);
        throw new Error("Failed to fetch training schedules.");
    }
};

export const createTrainingSchedule = async (scheduleData) => {
    try {
        const response = await apiClient.post(`/schedules`, scheduleData);
        return response.data;
    } catch (error) {
        console.error("Failed to create schedule:", error.response?.data || error.message);
        throw new Error("Failed to create training schedule.");
    }
};

export const deleteTrainingSchedule = async (scheduleId) => {
    try {
        await apiClient.delete(`/schedules/${scheduleId}`);
    } catch (error) {
        console.error("Failed to delete schedule:", error.response?.data || error.message);
        throw new Error("Failed to delete training schedule.");
    }
};

export const getTrainingRuns = async () => {
    try {
        const response = await apiClient.get(`/training-runs`);
        return response.data;
    } catch (error) {
        console.error("Failed to fetch training runs:", error.response?.data || error.message);
        throw new Error("Failed to fetch training runs.");
    }
};

export const getTrainingRunDetail = async (id) => {
    try {
        const response = await apiClient.get(`/training-runs/${id}`);
        return response.data;
    } catch (error) {
        console.error("Failed to fetch training run detail:", error.response?.data || error.message);
        throw new Error("Failed to fetch training run details.");
    }
};

export const deleteTrainingDoc = async (docId) => {
    try {
        await apiClient.delete(`/training-docs/${docId}`);
    } catch (error) {
        console.error("Failed to delete training doc:", error.response?.data || error.message);
        const errorMessage = error.response?.data?.detail || "Failed to delete document.";
        throw new Error(errorMessage);
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
        console.error("Failed to upload training doc:", error.response?.data || error.message);
        const errorMessage = error.response?.data?.detail || "Failed to upload document.";
        throw new Error(errorMessage);
    }
};

export const getTrainingStatus = async () => {
    try {
        const response = await apiClient.get(`/model-management/status`);
        return response.data;
    } catch (error) {
        console.error("Failed to fetch training status:", error.response?.data || error.message);
        throw new Error("Failed to fetch training status.");
    }
};

export const getLLMPromptSettings = async () => {
    try {
        const response = await apiClient.get(`/llm-prompt-settings`);
        return response.data;
    } catch (error) {
        console.error("Failed to fetch LLM prompt settings:", error.response?.data || error.message);
        throw new Error("Failed to fetch LLM prompt settings.");
    }
};

export const updateLLMPromptSettings = async (data) => {
    try {
        const response = await apiClient.patch(`/llm-prompt-settings`, data);
        return response.data;
    } catch (error) {
        console.error("Failed to update LLM prompt settings:", error.response?.data || error.message);
        throw new Error("Failed to update LLM prompt settings.");
    }
};

export const runManualTraining = async () => {
    try {
        const response = await apiClient.post(`/model-management/run-now`, {});
        return response.data;
    } catch (error) {
        console.error("Failed to start training:", error.response?.data || error.message);
        const errorMessage = error.response?.data?.detail || "Failed to start training process.";
        throw new Error(errorMessage);
    }
};
