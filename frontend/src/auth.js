import { betterAuth } from "better-auth";
import { APIError, createAuthEndpoint, createAuthMiddleware } from "better-auth/api";
import { getChunkedCookie, setCookieCache, setSessionCookie } from "better-auth/cookies";
import { symmetricDecodeJWT } from "better-auth/crypto";
import { customSession, genericOAuth } from "better-auth/plugins";
import { nextCookies } from "better-auth/next-js";
import * as z from "zod";

export const getSession = async () => {
    const { headers } = await import("next/headers");
    // Resolve the session in-process — no HTTP self-call, so no internal URL to
    // configure. auth.api.getSession applies the customSession transform (so
    // user.access_token is present); wrap it in { data } to match the shape the
    // caller previously got from authClient.getSession().
    const session = await auth.api.getSession({ headers: await headers() });
    return { data: session };
};

const SESSION_LIFETIME = 8 * 60 * 60; // 8 hours in seconds

function getApiBase() {
    // callDjango only runs server-side (inside better-auth endpoint handlers),
    // so reach the backend directly over the Docker network. The browser branch
    // falls back to a same-origin relative path and is effectively unused.
    const host =
        typeof window === "undefined"
            ? process.env.INTERNAL_API_HOST || "http://localhost:8000"
            : "";
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

// Mark the refresh cookie Secure only when actually served over HTTPS. Keying
// off NODE_ENV alone makes it Secure on HTTP-only prod deployments, where the
// browser silently drops it — breaking token refresh. Infer from the auth URL
// scheme, matching how better-auth decides its own cookie flags.
const USE_SECURE_COOKIES = (process.env.BETTER_AUTH_URL || "").startsWith(
    "https"
);

function setRefreshCookie(ctx, value) {
    ctx.setCookie(REFRESH_COOKIE, value, {
        httpOnly: true,
        secure: USE_SECURE_COOKIES,
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
                        djangoData = await callDjango("account/login", {
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
                        djangoData = await callDjango("account/token/refresh", {
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

                    const djangoData = await callDjango("account/microsoft", {
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
    account: {
        // better-auth defaults storeAccountCookie:true, which caches the OAuth
        // provider's tokens (Microsoft access_token/id_token/refresh_token) in a
        // chunked JWE `account_data` cookie. Azure AD tokens are large (group
        // claims etc.), so this balloons to hundreds of KB across chunks and the
        // browser replays them on every request -> nginx 400 "Request Header Or
        // Cookie Too Large". We never use the Microsoft tokens after login (the
        // callback exchanges them for Django JWTs once), so drop the cookie.
        storeAccountCookie: false,
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
            const { djangoAccessToken, djangoRefreshToken, ...safeUser } = user;
            return {
                user: {
                    ...safeUser,
                    access_token: djangoAccessToken,
                },
                session,
            };
        }),
        nextCookies(),
        ...(microsoftProvider ? [microsoftProvider] : []),
    ],
});
