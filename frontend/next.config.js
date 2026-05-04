/** @type {import('next').NextConfig} */
// In production we ship a static export served by FastAPI on the same origin,
// so rewrites are unnecessary (and unsupported in `output: 'export'` mode).
// During local development (`npm run dev`) we proxy /api/* to the backend
// running on :8000 to avoid CORS while keeping all fetch calls origin-relative
// in component code. We toggle the export mode based on NODE_ENV so dev mode
// keeps rewrites and prod build emits the static bundle into ./out.
const isProd = process.env.NODE_ENV === 'production';

const nextConfig = {
  reactStrictMode: true,
  trailingSlash: false,
  images: {
    unoptimized: true,
  },
  ...(isProd
    ? { output: 'export' }
    : {
        async rewrites() {
          return [
            {
              source: '/api/:path*',
              destination: 'http://localhost:8000/api/:path*',
            },
          ];
        },
      }),
};

module.exports = nextConfig;
