const isDev = process.env.NODE_ENV !== 'production';

// Content-Security-Policy. The Django JWT is readable by client JS (it's set as
// an Authorization header, not an httpOnly cookie), so any script injection can
// exfiltrate it — this policy is the defence-in-depth layer around that.
//
// It's a *moderate* policy: it pins scripts/styles/images/connections to the
// app's own origin and shuts down the classic clickjacking / <base> / form-
// hijack vectors. `script-src` still allows 'unsafe-inline' because Next.js
// emits inline bootstrap scripts and we don't yet mint a per-request nonce —
// tightening script-src to a nonce (via middleware) is the recommended
// follow-up. 'unsafe-inline' for styles is required by MUI/emotion. 'unsafe-eval'
// and the ws: connect source are dev-only (React Fast Refresh / HMR).
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ''}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${isDev ? ' ws:' : ''}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'self'",
  "frame-src 'none'",
].join('; ');

const securityHeaders = [
  { key: 'Content-Security-Policy', value: contentSecurityPolicy },
  { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
];

// Backend origin for server-side proxying. In Docker this is the compose
// service (http://backend:8000); in bare local dev it defaults to :8000.
const BACKEND_ORIGIN = process.env.INTERNAL_API_HOST || 'http://localhost:8000';

const nextConfig = {
  output: 'standalone',
  async headers() {
    return [{ source: '/(.*)', headers: securityHeaders }];
  },
  // The browser talks to its own origin via relative URLs. In production nginx
  // routes these to Django before they reach Next, so the rewrites never fire
  // there. In local dev (no nginx) they proxy to the backend so the same
  // relative URLs work. Everything under /api goes to Django EXCEPT /api/auth/*,
  // which belongs to better-auth (the Next [...betterauth] catch-all). NOTE:
  // `afterFiles` rewrites are matched BEFORE dynamic routes, so a blanket
  // /api/:path* would swallow /api/auth/* — hence the negative lookahead.
  async rewrites() {
    return {
      afterFiles: [
        {
          source: '/api/:path((?!auth/).*)',
          destination: `${BACKEND_ORIGIN}/api/:path(.*)`,
        },
        { source: '/media/:path*', destination: `${BACKEND_ORIGIN}/media/:path*` },
      ],
    };
  },
  ...(process.env.CYPRESS_TEST
    ? {}
    : {
        turbopack: {},
      }),
  webpack(config) {
    if (process.env.CYPRESS_TEST) {
      config.module.rules.push({
        test: /\.(js|ts|jsx|tsx)$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader",
          options: {
            presets: ["next/babel"],
            plugins: ["istanbul"],
          },
        },
      });
    }
    return config;
  },
};

export default nextConfig;