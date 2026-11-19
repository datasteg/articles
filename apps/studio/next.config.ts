import type { NextConfig } from 'next';

// The video studio: a local dev server only (`artools video slides` starts it on 127.0.0.1:3313 and screenshots it).
const config: NextConfig = {
  transpilePackages: ['@glacier/ui', '@glacier/i18n', '@glacier/fonts', '@glacier/tokens', '@articles/charts'],
  allowedDevOrigins: ['127.0.0.1'],
  poweredByHeader: false,
  devIndicators: false,
};

export default config;
