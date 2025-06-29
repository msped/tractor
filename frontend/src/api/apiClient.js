import axios from "axios";

const apiClient = () => {
    const defaultOptions = {
        baseURL: `${process.env.NEXT_PUBLIC_API_HOST}/api`,
        headers: {
            "Content-Type": "application/json",
            accept: "application/json",
        },
    }
    
    const instance = axios.create(defaultOptions);

    instance.interceptors.response.use(
        (response) => {
            return response;
        },
        (error) => {
            if (typeof window !== 'undefined' && error.response?.status === 401) {
                window.location.href = '/';
            }
            return Promise.reject(error);
        }
    )

    return instance;
}

export default apiClient();