import { createAuthClient } from "better-auth/react";
import { genericOAuthClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
    baseURL:
        (typeof window !== "undefined"
            ? process.env.NEXT_PUBLIC_BETTER_AUTH_URL
            : process.env.BETTER_AUTH_URL) || "http://localhost:3000",
    basePath: "/api/auth",
    plugins: [genericOAuthClient()],
});
