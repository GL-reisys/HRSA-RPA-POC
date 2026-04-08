/** @type {import('next').NextConfig} */
const apiInternalUrl = (process.env.API_INTERNAL_URL || 'http://127.0.0.1:5000').replace(/\/$/, '');

const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiInternalUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
