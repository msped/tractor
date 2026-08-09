import axios from "axios";
import { authClient } from "@/lib/auth-client.base";

let isRefreshing = false;
let refreshSubscribers = [];
let clientToken = null;

export function setClientToken(token) {
    clientToken = token;
}

function onRefreshed(token) {
    refreshSubscribers.forEach(({ onSuccess }) => onSuccess(token));
    refreshSubscribers = [];
}

// Requests queued behind an in-flight refresh must be settled when that refresh
// fails, not dropped. Clearing the array without calling anything left their
// promises pending forever, so the UI sat on a spinner with no error.
function onRefreshFailed(error) {
    refreshSubscribers.forEach(({ onFailure }) => onFailure(error));
    refreshSubscribers = [];
}

const REFRESH_TIMEOUT_MS = 15000;

const apiClient = () => {
    // Server-side (Next.js container): use INTERNAL_API_HOST to reach the
    // backend directly on the Docker network. Client-side (browser): use a
    // relative URL so the request goes to whatever origin served the app
    // (nginx path-routes /api to the backend). This keeps the browser bundle
    // origin-agnostic — no NEXT_PUBLIC_API_HOST baked in at build time.
    const host = typeof window === 'undefined'
        ? (process.env.INTERNAL_API_HOST || 'http://localhost:8000')
        : '';
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
                window.location.href = '/api/auth/force-logout';
                return new Promise(() => {});
            }

            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    refreshSubscribers.push({
                        onSuccess: token => {
                            originalRequest.headers.Authorization = `Bearer ${token}`;
                            resolve(instance(originalRequest));
                        },
                        onFailure: reject,
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
                    // Send a JSON body so better-fetch sets Content-Type:
                    // application/json. Without it better-auth rejects the POST
                    // with 415 (Unsupported Media Type) before the handler runs.
                    body: {},
                    fetchOptions: { signal: controller.signal },
                });
                if (result.error) {
                    const refreshError = new Error(
                        result.error.message || 'Session refresh failed.'
                    );
                    refreshError.status = result.error.status;
                    throw refreshError;
                }

                const newToken = result.data?.access_token;
                clientToken = newToken;
                onRefreshed(newToken);
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
                return instance(originalRequest);
            } catch (refreshError) {
                // Only end the session when the refresh token itself was
                // rejected. A backend outage, or the 15s abort above, used to
                // hit this same branch and log the user out — indistinguishable
                // from a genuine expiry, and it lost their unsaved work.
                const sessionIsSpent = refreshError.status === 401;

                clientToken = null;

                if (!sessionIsSpent) {
                    console.error('Token refresh failed; keeping session.', refreshError);
                    onRefreshFailed(refreshError);
                    return Promise.reject(refreshError);
                }

                onRefreshFailed(refreshError);
                window.location.href = '/api/auth/force-logout';
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
