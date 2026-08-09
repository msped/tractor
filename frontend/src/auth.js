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

/**
 * A Django call that failed, carrying enough detail to tell apart "the user
 * typed the wrong password" from "the backend is unreachable".
 *
 * `kind` is what callers branch on:
 *   credentials — Django rejected the request (400/401); the user's input is wrong
 *   throttled   — Django's rate limiter kicked in (429)
 *   upstream    — Django is reachable but broken (5xx, or any other non-2xx)
 *   network     — the request never got an HTTP response (DNS, TCP, TLS, timeout)
 *
 * The `network` case is the one that caused a production outage to be
 * misreported as bad credentials: SECURE_SSL_REDIRECT 301'd the internal
 * plain-HTTP call, the TLS handshake failed, fetch threw, and the old
 * catch-all turned that into "Invalid username or password".
 */
class DjangoCallError extends Error {
    constructor(kind, message, { status = null, cause = null } = {}) {
        super(message, { cause });
        this.name = "DjangoCallError";
        this.kind = kind;
        this.status = status;
    }
}

function classifyStatus(status) {
    if (status === 400 || status === 401 || status === 403) {
        return "credentials";
    }
    if (status === 429) return "throttled";
    return "upstream";
}

async function callDjango(path, body) {
    const url = `${getApiBase()}/${path}`;

    let res;
    try {
        res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
    } catch (cause) {
        // fetch only rejects when no HTTP response was produced at all.
        throw new DjangoCallError(
            "network",
            `Could not reach the backend at ${url}: ${cause.message}`,
            { cause }
        );
    }

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new DjangoCallError(
            classifyStatus(res.status),
            err.detail || `Django responded ${res.status} for ${path}`,
            { status: res.status }
        );
    }

    return res.json();
}

/**
 * Turn a failed Django call into the response the browser should see, and make
 * sure the real cause is written to the server log first.
 *
 * The user-facing message stays deliberately vague for infrastructure failures
 * (no internal hostnames or stack detail), but the log line keeps everything
 * needed to diagnose it.
 */
function authFailure(error, context) {
    const kind = error instanceof DjangoCallError ? error.kind : "upstream";

    console.error(
        `[auth] ${context} failed (kind=${kind}, status=${error?.status ?? "none"}): ${error?.message}`,
        error?.cause ?? ""
    );

    switch (kind) {
        case "credentials":
            return APIError.from(
                "UNAUTHORIZED",
                "Invalid username or password."
            );
        case "throttled":
            return APIError.from(
                "TOO_MANY_REQUESTS",
                "Too many sign-in attempts. Please wait a minute and try again."
            );
        default:
            // network / upstream: the user's credentials may be perfectly fine,
            // so never tell them to check them.
            return APIError.from(
                "SERVICE_UNAVAILABLE",
                "Sign-in is temporarily unavailable. Please try again shortly."
            );
    }
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
                    } catch (error) {
                        throw authFailure(error, "password sign-in");
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
                    } catch (error) {
                        // The status matters to the caller: 401 means the
                        // refresh token really is spent and the session should
                        // end, while 503 means the backend blipped and the
                        // client should keep the session and retry. Collapsing
                        // both into UNAUTHORIZED logged everyone out whenever
                        // Django restarted.
                        throw authFailure(error, "token refresh");
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
                    let graphRes;
                    try {
                        graphRes = await fetch(
                            "https://graph.microsoft.com/v1.0/me",
                            {
                                headers: {
                                    Authorization: `Bearer ${accessToken}`,
                                },
                            }
                        );
                    } catch (cause) {
                        console.error(
                            `[auth] Microsoft Graph unreachable: ${cause.message}`,
                            cause
                        );
                        throw APIError.from(
                            "SERVICE_UNAVAILABLE",
                            "Could not reach Microsoft. Please try again shortly."
                        );
                    }

                    if (!graphRes.ok) {
                        const body = await graphRes.text().catch(() => "");
                        console.error(
                            `[auth] Microsoft Graph responded ${graphRes.status}: ${body.slice(0, 500)}`
                        );
                        throw APIError.from(
                            "BAD_REQUEST",
                            "Microsoft sign-in failed. Please try again."
                        );
                    }
                    const graphUser = await graphRes.json();

                    // Previously uncaught: a Django failure here surfaced as a
                    // raw OAuth error with no server-side log, a third distinct
                    // shape alongside the password and refresh paths.
                    let djangoData;
                    try {
                        djangoData = await callDjango("account/microsoft", {
                            access_token: accessToken,
                        });
                    } catch (error) {
                        throw authFailure(error, "Microsoft sign-in");
                    }

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
