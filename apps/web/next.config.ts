import type { NextConfig } from "next";
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin();

function _getApiBaseUrlForRewrites(): string {
  const apiBaseUrl =
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    '';

  const isStandalone = process.env.BUILD_STANDALONE === '1';
  if (isStandalone && !apiBaseUrl) {
    throw new Error(
      "[next.config] BUILD_STANDALONE=1 requires API_BASE_URL (or NEXT_PUBLIC_API_BASE_URL) to be set. " +
      "Desktop packaging: set API_BASE_URL=http://127.0.0.1:8000. " +
      "Docker/compose: set API_BASE_URL=http://core:8000."
    );
  }

  return apiBaseUrl;
}

/** @type {import('next').NextConfig} */
const nextConfig: NextConfig = {
  // Enable standalone output for Electron production packaging.
  // In standalone mode, Next.js produces a self-contained server at
  // .next/standalone/server.js that Electron's main process can spawn directly.
  // This does NOT affect local web development (next dev / next start work as usual).
  ...(process.env.BUILD_STANDALONE === '1' && { output: 'standalone' }),

  async rewrites() {
    const apiBaseUrl = _getApiBaseUrlForRewrites();

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
