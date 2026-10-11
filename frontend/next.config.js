/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  experimental: {
    serverActions: { bodySizeLimit: '2mb' },
  },
  async rewrites() {
    return [
      { source: '/api/backend/:path*', destination: 'http://backend:8000/:path*' },
    ];
  },
};

module.exports = nextConfig;