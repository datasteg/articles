import path from 'node:path';
import type { NextConfig } from 'next';

const config: NextConfig = {
  // A self-contained server (node server.js) for the container image.
  output: 'standalone',
  // Monorepo: trace files from the app folder's root so the workspace packages are included.
  outputFileTracingRoot: path.join(__dirname, '../..'),
  transpilePackages: ['@glacier/ui', '@glacier/i18n', '@glacier/fonts', '@glacier/tokens', '@articles/charts'],
  images: { unoptimized: true },
  // `artools render` loads the dev preview from 127.0.0.1; without this the client bundle is blocked and charts never hydrate.
  allowedDevOrigins: ['127.0.0.1'],
  poweredByHeader: false,
  // The one-topic pages were retired on 21 Oct 2026: the home page filters by topic in place (?topic=).
  async redirects() {
    return [{ source: '/:lang(en|ko)/topics/:id', destination: '/:lang?topic=:id', permanent: false }];
  },
  env: {
    APP_VERSION: process.env.APP_VERSION ?? 'dev',
    BUILD_TIME: process.env.BUILD_TIME ?? new Date().toISOString(),
  },
};

export default config;
