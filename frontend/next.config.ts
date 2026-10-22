import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Self-contained server bundle (.next/standalone) so the host only needs Node.
  output: 'standalone',
};

export default nextConfig;
