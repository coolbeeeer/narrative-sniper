/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    serverActions: { bodySizeLimit: '2mb' },
  },
  async rewrites() {
    return [
      { source: '/api/backend/:path*', destination: 'http://localhost:8000/:path*' },
      { source: '/ws/backend', destination: 'ws://localhost:8000/ws' },
    ];
  },
};

module.exports = nextConfig;