import type { MetadataRoute } from 'next';
import { LANGS } from '@glacier/i18n';
import { ARTICLES, GLOSSARY, IS_PREVIEW, PIPELINES, editionsOf } from '@/lib/content';

// GET /sitemap.xml: every page in both languages, each with its hreflang twins. Built once, at build time.
// An article is listed only in the languages it has: the other language's page shows the same edition, canonical to it.
const SITE = 'https://articles.datasteg.com';

type Entry = MetadataRoute.Sitemap[number];
const page = (path: string, langs: readonly string[], lastModified?: string): Entry[] =>
  langs.map((lang) => ({
    url: `${SITE}/${lang}${path}`,
    ...(lastModified ? { lastModified } : {}),
    alternates: { languages: Object.fromEntries(langs.map((l) => [l, `${SITE}/${l}${path}`])) },
  }));

export default function sitemap(): MetadataRoute.Sitemap {
  if (IS_PREVIEW) return [];
  const latest = ARTICLES[0]?.meta.updated ?? ARTICLES[0]?.meta.date;
  return [
    ...page('', LANGS, latest),
    ...ARTICLES.flatMap((a) => page(`/a/${a.slug}`, editionsOf(a), a.meta.updated ?? a.meta.date)),
    ...['/topics', '/glossary', '/about', '/method', '/privacy', '/terms'].flatMap((p) => page(p, LANGS)),
    ...PIPELINES.flatMap((p) => [...page(`/method/${p.id}`, LANGS), ...page(`/formats/${p.id}`, LANGS)]),
    ...Object.keys(GLOSSARY).flatMap((id) => page(`/glossary/${id}`, LANGS)),
  ];
}
