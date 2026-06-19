import axios from "axios";
import { authClient } from "@/lib/auth-client";

let isRefreshing = false;
let refreshSubscribers = [];
let clientToken = null;

export function setClientToken(token) {
    clientToken = token;
}

function onRefreshed(token) {
    refreshSubscribers.forEach(cb => cb(token));
    refreshSubscribers = [];
}

const REFRESH_TIMEOUT_MS = 15000;

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

    instance.interceptors.request.use(async (config) => {
        if (config.data instanceof FormData) {
            delete config.headers['Content-Type'];
        }

        let token;
        if (typeof window === 'undefined') {
            try {
                const { getSession } = await import('@/auth');
                const { data } = await getSession();
                token = data?.user?.access_token;
            } catch {
                // outside Next.js request context
            }
        } else {
            // Use cached token from SessionContext; fall back to getSession on first load
            if (clientToken !== null) {
                token = clientToken;
            } else {
                const { data } = await authClient.getSession();
                token = data?.user?.access_token ?? null;
                clientToken = token;
            }
        }
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    });

    instance.interceptors.response.use(
        (response) => response,
        async (error) => {
            if (typeof window === 'undefined' || window.Cypress || error.response?.status !== 401) {
                return Promise.reject(error);
            }

            const originalRequest = error.config;
            if (originalRequest._retried) {
                window.location.href = '/api/force-logout';
                return new Promise(() => {});
            }

            if (isRefreshing) {
                return new Promise(resolve => {
                    refreshSubscribers.push(token => {
                        originalRequest.headers.Authorization = `Bearer ${token}`;
                        resolve(instance(originalRequest));
                    });
                });
            }

            originalRequest._retried = true;
            isRefreshing = true;

            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS);

            try {
                const result = await authClient.$fetch("/refresh-django-token", {
                    method: "POST",
                    fetchOptions: { signal: controller.signal },
                });
                if (result.error) throw new Error("Refresh failed");

                const newToken = result.data?.access_token;
                clientToken = newToken;
                onRefreshed(newToken);
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
                return instance(originalRequest);
            } catch {
                clientToken = null;
                refreshSubscribers = [];
                window.location.href = '/api/force-logout';
                return new Promise(() => {});
            } finally {
                clearTimeout(timeout);
                isRefreshing = false;
            }
        }
    )

    return instance;
}

export default apiClient();
