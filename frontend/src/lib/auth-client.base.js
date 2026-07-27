import { createAuthClient } from "better-auth/client";
import { genericOAuthClient } from "better-auth/client/plugins";

// Framework-agnostic (hook-free) better-auth client. Safe to import from
// modules that are reachable server-side (e.g. apiClient.js): unlike
// better-auth/react it pulls in no React hooks, so it never resolves `react`
// via the RSC `react-server` condition (which omits useRef/useSyncExternalStore
// and breaks the webpack production build). Use @/lib/auth-client (the React
// client) only from "use client" components that need useSession().
//
// This client is only invoked in the browser (session fetch + token refresh in
// apiClient.js) — server-side session reads go through auth.api.getSession()
// in-process. Browser baseURL is the current origin, so the bundle stays
// origin-agnostic; the server fallback below is only for module evaluation and
// is never actually called.
export const authClient = createAuthClient({
    baseURL:
        typeof window !== "undefined"
            ? window.location.origin
            : process.env.BETTER_AUTH_URL || "http://localhost:3000",
    basePath: "/api/auth",
    plugins: [genericOAuthClient()],
});
