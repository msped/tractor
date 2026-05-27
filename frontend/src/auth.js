import { betterAuth } from "better-auth";
import { APIError, createAuthEndpoint, createAuthMiddleware } from "better-auth/api";
import { getChunkedCookie, setCookieCache, setSessionCookie } from "better-auth/cookies";
import { symmetricDecodeJWT } from "better-auth/crypto";
import { customSession, genericOAuth } from "better-auth/plugins";
import { nextCookies } from "better-auth/next-js";
import * as z from "zod";

export const getSession = async () => {
    const { headers } = await import("next/headers");
    const { authClient } = await import("@/lib/auth-client");
    return authClient.getSession({
        fetchOptions: { headers: await headers() },
    });
};

const SESSION_LIFETIME = 8 * 60 * 60; // 8 hours in seconds

function getApiBase() {
    const host =
        typeof window === "undefined"
            ? process.env.INTERNAL_API_HOST ||
              process.env.NEXT_PUBLIC_API_HOST ||
              ""
            : process.env.NEXT_PUBLIC_API_HOST || "";
    return `${host}/api`;
}

async function callDjango(path, body) {
    const res = await fetch(`${getApiBase()}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Authentication failed");
    }
    return res.json();
}

const REFRESH_COOKIE = "django_rt";
const REFRESH_COOKIE_MAX_AGE = 24 * 60 * 60;

function setRefreshCookie(ctx, value) {
    ctx.setCookie(REFRESH_COOKIE, value, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: REFRESH_COOKIE_MAX_AGE,
        path: "/",
    });
}

function parseRefreshCookie(cookieHeader) {
    if (!cookieHeader) return null;
    const match = cookieHeader.match(
        new RegExp(`(?:^|;\\s*)${REFRESH_COOKIE}=([^;]*)`)
    );
    return match ? decodeURIComponent(match[1]) : null;
}

function djangoCredentialsPlugin() {
    return {
        id: "django-credentials",
        endpoints: {
            signInUsername: createAuthEndpoint(
                "/sign-in/username",
                {
                    method: "POST",
                    body: z.object({
                        username: z.string(),
                        password: z.string(),
                    }),
                },
                async (ctx) => {
                    const { username, password } = ctx.body;

                    let djangoData;
                    try {
                        djangoData = await callDjango("auth/login", {
                            username,
                            password,
                        });
                    } catch {
                        throw APIError.from(
                            "UNAUTHORIZED",
                            "Invalid username or password"
                        );
                    }

                    const email =
                        djangoData.user?.email || `${username}@internal`;
                    const name = djangoData.user?.username || username;

                    const existing =
                        await ctx.context.internalAdapter.findUserByEmail(
                            email
                        );
                    let user;
                    const isAdmin =
                        (djangoData.user?.is_staff || djangoData.user?.is_superuser) ?? false;

                    if (existing?.user) {
                        user =
                            (await ctx.context.internalAdapter.updateUser(
                                existing.user.id,
                                {
                                    djangoAccessToken: djangoData.access,
                                    djangoRefreshToken: djangoData.refresh,
                                    isAdmin,
                                }
                            )) || existing.user;
                    } else {
                        user = await ctx.context.internalAdapter.createUser({
                            email,
                            name,
                            emailVerified: true,
                            djangoAccessToken: djangoData.access,
                            djangoRefreshToken: djangoData.refresh,
                            isAdmin,
                        });
                    }

                    const session =
                        await ctx.context.internalAdapter.createSession(
                            user.id
                        );
                    await setSessionCookie(ctx, { session, user });

                    return ctx.json({ user, token: session.token });
                }
            ),
            refreshDjangoToken: createAuthEndpoint(
                "/refresh-django-token",
                { method: "POST" },
                async (ctx) => {
                    const cookieHeader = ctx.request.headers.get("cookie");
                    const refreshToken = parseRefreshCookie(cookieHeader);
                    if (!refreshToken) {
                        throw APIError.from("UNAUTHORIZED", "No refresh token");
                    }

                    const sessionDataCookie = getChunkedCookie(
                        ctx,
                        ctx.context.authCookies.sessionData.name
                    );
                    if (!sessionDataCookie) {
                        throw APIError.from("UNAUTHORIZED", "No session");
                    }

                    const payload = await symmetricDecodeJWT(
                        sessionDataCookie,
                        ctx.context.secretConfig,
                        "better-auth-session"
                    );
                    if (!payload?.session || !payload?.user) {
                        throw APIError.from("UNAUTHORIZED", "Invalid session");
                    }

                    let djangoData;
                    try {
                        djangoData = await callDjango("auth/token/refresh", {
                            refresh: refreshToken,
                        });
                    } catch {
                        throw APIError.from(
                            "UNAUTHORIZED",
                            "Django token refresh failed"
                        );
                    }

                    await setCookieCache(ctx, {
                        session: payload.session,
                        user: {
                            ...payload.user,
                            djangoAccessToken: djangoData.access,
                        },
                    });

                    if (djangoData.refresh) {
                        setRefreshCookie(ctx, djangoData.refresh);
                    }

                    return ctx.json({ access_token: djangoData.access });
                }
            ),
        },
        hooks: {
            after: [
                {
                    matcher: (ctx) =>
                        !!ctx.context.newSession?.user?.djangoRefreshToken,
                    handler: createAuthMiddleware(async (ctx) => {
                        setRefreshCookie(
                            ctx,
                            ctx.context.newSession.user.djangoRefreshToken
                        );
                    }),
                },
            ],
        },
    };
}

function buildMicrosoftProvider() {
    if (
        !process.env.BETTER_AUTH_MICROSOFT_CLIENT_ID ||
        !process.env.BETTER_AUTH_MICROSOFT_CLIENT_SECRET
    )
        return null;

    const tenantId =
        process.env.BETTER_AUTH_MICROSOFT_TENANT_ID || "common";

    return genericOAuth({
        config: [
            {
                providerId: "microsoft",
                clientId: process.env.BETTER_AUTH_MICROSOFT_CLIENT_ID,
                clientSecret:
                    process.env.BETTER_AUTH_MICROSOFT_CLIENT_SECRET,
                authorizationUrl: `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize`,
                tokenUrl: `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
                scopes: ["openid", "profile", "email", "User.Read"],
                getUserInfo: async ({ accessToken }) => {
                    const graphRes = await fetch(
                        "https://graph.microsoft.com/v1.0/me",
                        {
                            headers: {
                                Authorization: `Bearer ${accessToken}`,
                            },
                        }
                    );
                    if (!graphRes.ok)
                        throw APIError.from(
                            "BAD_REQUEST",
                            "Microsoft Graph request failed"
                        );
                    const graphUser = await graphRes.json();

                    const djangoData = await callDjango("auth/microsoft", {
                        access_token: accessToken,
                    });

                    return {
                        id: graphUser.id,
                        email:
                            graphUser.mail || graphUser.userPrincipalName,
                        name: graphUser.displayName,
                        emailVerified: true,
                        djangoAccessToken: djangoData.access,
                        djangoRefreshToken: djangoData.refresh,
                        isAdmin:
                            (djangoData.user?.is_staff ||
                                djangoData.user?.is_superuser) ??
                            false,
                    };
                },
            },
        ],
    });
}

const microsoftProvider = buildMicrosoftProvider();

export const auth = betterAuth({
    secret: process.env.BETTER_AUTH_SECRET,
    baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3000",
    rateLimit: {
        window: 60,
        max: 100,
        customRules: {
            "/sign-in/username": { window: 60, max: 5 },
        },
    },
    session: {
        expiresIn: SESSION_LIFETIME,
        cookieCache: {
            enabled: true,
            maxAge: SESSION_LIFETIME,
            strategy: "jwe",
        },
    },
    user: {
        additionalFields: {
            djangoAccessToken: {
                type: "string",
                required: false,
                returned: true,
            },
            djangoRefreshToken: {
                type: "string",
                required: false,
                returned: false,
            },
            isAdmin: {
                type: "boolean",
                required: false,
                returned: true,
                defaultValue: false,
            },
        },
    },
    plugins: [
        djangoCredentialsPlugin(),
        customSession(async ({ user, session }) => {
            const { djangoAccessToken, djangoRefreshToken, isAdmin, ...safeUser } = user;
            return {
                user: {
                    ...safeUser,
                    access_token: djangoAccessToken,
                    is_admin: isAdmin ?? false,
                },
                session,
            };
        }),
        nextCookies(),
        ...(microsoftProvider ? [microsoftProvider] : []),
    ],
});
