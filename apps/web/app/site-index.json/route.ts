// GET /site-index.json: what is live, for the admin site to count and list.
// Public information only: the same titles, dates and topics the pages show. Built once, at build time.
import { LANGS } from '@glacier/i18n';
import { ARTICLES, GLOSSARY, TOPICS } from '@/lib/content';

export const dynamic = 'force-static';

/** Text without citation markers ([[S4]]) and with glossary marks ((spread|the spread)) as their words. */
const plain = (s: string) => s.replace(/\[\[[^\]]*\]\]|\(\(([^)|]+)\|?([^)]*)\)\)/g, (_, id, text) => text || id || '');

export function GET() {
  return Response.json({
    service: 'articles',
    version: process.env.APP_VERSION ?? 'dev',
    built: process.env.BUILD_TIME,
    articles: ARTICLES.map((a) => ({
      slug: a.slug,
      type: a.meta.type,
      date: a.meta.date,
      updated: a.meta.updated ?? null,
      editions: LANGS.filter((l) => a.editions[l]),
      title: Object.fromEntries(LANGS.filter((l) => a.editions[l]).map((l) => [l, a.editions[l]!.title])),
      kicker: Object.fromEntries(LANGS.filter((l) => a.editions[l]).map((l) => [l, a.editions[l]!.kicker])),
      dek: Object.fromEntries(LANGS.filter((l) => a.editions[l]).map((l) => [l, plain(a.editions[l]!.dek)])),
      topics: a.meta.topics.map((t) => t.id),
      pdf: LANGS.filter((l) => a.meta.pdf?.[l]?.url),
      corrections: a.meta.corrections?.length ?? 0,
    })),
    glossary: Object.keys(GLOSSARY).length,
    topics: TOPICS.filter((t) => t.articles.length).length,
  });
}
