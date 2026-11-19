// GET /svc/v1/item?id=<kind>:<key>&lang=: one item as readable Markdown for the cross-app fetch tool: an article
// (kind article, the whole edition, at most 20,000 characters) or a glossary term (kind term).
import { tx } from '@articles/charts';
import { GLOSSARY, editionOf, getArticle } from '@/lib/content';
import { SLUG, articleMarkdown, articleSummary, envelope, listItem, pageOf, reuseNote, sourceOut, termOut } from '@/lib/svc-articles';
import { s } from '@/lib/strings';
import { svcError, svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const denied = svcGuard(req); if (denied) return denied;
  const url = new URL(req.url);
  const lang = svcLang(url);
  const id = url.searchParams.get('id') || '';
  const m = id.match(/^([a-z]+):(.+)$/);
  if (!m || !['article', 'term'].includes(m[1])) return svcError(400, 'bad-parameter', 'Unknown item kind', `id is <kind>:<key> with kind article or term, such as article:won-after-rate-hold or term:spread; got "${id.slice(0, 80)}".`);
  const [, kind, key] = m;
  if (kind === 'article') {
    const a = SLUG.test(key) ? getArticle(key) : undefined;
    if (!a) return svcError(404, 'unknown-article', 'Unknown article', `${key.slice(0, 100)} is not the slug of a published datasteg article. The articles view lists them.`);
    const { ed, lang: el } = editionOf(a, lang);
    const { text, cut } = articleMarkdown(a, lang);
    const li = listItem(a, lang);
    return svcJson(envelope('item', lang, {
      page: pageOf(a, lang), summary: articleSummary(a),
      data: {
        id, title: ed.title, text,
        metadata: { kind, slug: a.slug, url: `https://articles.datasteg.com${pageOf(a, lang)}`, edition: el, type: li.type, date: li.date, updated: li.updated,
          topics: li.topics.map((t) => t.id), countries: li.countries, citation: a.meta.citation ? tx(a.meta.citation.url, el) : null, truncated: cut.length > 0 },
      },
      sources: a.sources.map((x) => sourceOut(x, el, { brief: true })),
      notes: [reuseNote(lang), ...(cut.length ? [`Left out of this text to keep it within 20,000 characters: ${cut.join('; ')}. The article view returns every section.`] : [])],
    }));
  }
  const g = GLOSSARY[key];
  if (!g) return svcError(404, 'unknown-term', 'Unknown term', `${key.slice(0, 100)} is not a glossary term id. The glossary view lists them (ids such as spread).`);
  const t = termOut(g, lang);
  const other = lang === 'ko' ? 'en' : 'ko';
  const alt = (t as Record<string, unknown>)[`term_${other}`] as string | null;
  const uses = g.articles.map((slug) => getArticle(slug)).filter((a) => a !== undefined).map((a) => {
    const ctx = a.terms.find((x) => x.id === g.id)?.context;
    return `- [${editionOf(a, lang).ed.title}](https://articles.datasteg.com${pageOf(a, lang)})${ctx ? `: ${tx(ctx, lang)}` : ''}`;
  });
  const see = (g.see ?? []).filter((k) => GLOSSARY[k]).map((k) => tx(GLOSSARY[k].term, lang));
  const text = [`# ${t.term}${alt ? ` (${alt})` : ''}`, t.definition, uses.length ? `## ${s(lang, 'gl.inArticles')}\n\n${uses.join('\n')}` : '',
    see.length ? `## ${s(lang, 'gl.related')}\n\n${see.map((x) => `- ${x}`).join('\n')}` : ''].filter(Boolean).join('\n\n');
  return svcJson(envelope('item', lang, {
    page: t.page, summary: `“${tx(g.term, 'en')}” in the datasteg articles glossary: ${tx(g.definition, 'en')}`,
    data: { id, title: t.term, text, metadata: { kind, term_id: g.id, url: `https://articles.datasteg.com${t.page}`, topics: t.topics, articles: t.articles, see: t.see } },
    notes: [reuseNote(lang)],
  }));
}
