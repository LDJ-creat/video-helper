import type { NextConfig } from "next";
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin();

/** @type {import('next').NextConfig} */
const nextConfig: NextConfig = {
  // Enable standalone output for Electron production packaging.
  // In standalone mode, Next.js produces a self-contained server at
  // .next/standalone/server.js that Electron's main process can spawn directly.
  // This does NOT affect local web development (next dev / next start work as usual).
  ...(process.env.BUILD_STANDALONE === '1' && { output: 'standalone' }),

  async rewrites() {
    const apiBaseUrl =
      process.env.API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      // Desktop packaging builds (standalone) must proxy to the local backend,
      // even in CI environments where .env.local is not present.
      (process.env.BUILD_STANDALONE === '1' ? 'http://127.0.0.1:8000' : '');

    if (!apiBaseUrl) return [];

    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBaseUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
