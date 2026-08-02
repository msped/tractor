import { createAuthClient } from "better-auth/react";
import { genericOAuthClient } from "better-auth/client/plugins";

// Browser: use the current origin (same-origin, no build-time URL baked in).
// SSR fallback: the public BETTER_AUTH_URL. useSession() only runs client-side,
// so the browser branch is what actually matters here.
export const authClient = createAuthClient({
    baseURL:
        typeof window !== "undefined"
            ? window.location.origin
            : process.env.BETTER_AUTH_URL || "http://localhost:3000",
    basePath: "/api/auth",
    plugins: [genericOAuthClient()],
});
