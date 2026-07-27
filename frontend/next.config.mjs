const securityHeaders = [
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