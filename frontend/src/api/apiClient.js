import axios from "axios";

const apiClient = () => {
    // Server-side (Next.js container): use INTERNAL_API_HOST to reach the
    // backend directly on the Docker network. Client-side (browser): use
    // NEXT_PUBLIC_API_HOST which resolves via nginx on the host machine.
    const host = typeof window === 'undefined'
        ? (process.env.INTERNAL_API_HOST || process.env.NEXT_PUBLIC_API_HOST || '')
        : (process.env.NEXT_PUBLIC_API_HOST || '');
    const defaultOptions = {
        baseURL: `${host}/api`,
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