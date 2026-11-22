// Server-side calls to Django go straight to the backend container over the
// Docker network, skipping nginx, so nothing adds X-Forwarded-Proto. With
// USE_HTTPS on, Django's SECURE_SSL_REDIRECT then sees plain HTTP and 301s the
// call to https://backend:8000, which has no TLS — login fails as "temporarily
// unavailable". Tell Django the scheme the public site is served on, inferred
// from BETTER_AUTH_URL the same way auth.js decides its cookies' Secure flag.
export function internalApiHeaders(publicUrl = process.env.BETTER_AUTH_URL) {
    return (publicUrl || "").startsWith("https")
        ? { "X-Forwarded-Proto": "https" }
        : {};
}
