import type { MetadataRoute } from 'next';
import { IS_PREVIEW } from '@/lib/content';

// Open to search engines since 28 Oct 2026; a preview build of
// unapproved drafts stays closed. Print pages are not disallowed: crawlers must read them to see their noindex.
export default function robots(): MetadataRoute.Robots {
  if (IS_PREVIEW) return { rules: [{ userAgent: '*', disallow: '/' }] };
  return {
    // /svc/ answers only the datasteg API service on the internal network
    rules: [{ userAgent: '*', allow: '/', disallow: '/svc/' }],
    sitemap: 'https://articles.datasteg.com/sitemap.xml',
  };
}
