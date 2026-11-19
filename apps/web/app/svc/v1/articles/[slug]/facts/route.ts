// GET /svc/v1/articles/{slug}/facts?chart=&limit=&cursor=&lang=: the article's numbered facts (the numbers its text
// renders, unrounded, with unit, period and the sources each was computed from) and, with chart=, that chart's data
// (the rows of its public CSV) and metadata. Facts the analysis blocked (publishable false) are never listed.
import { getArticle } from '@/lib/content';
import { SLUG, chartOut, chartTable, envelope, factOut, intParam, listItem, pageOf, publishedFacts, reuseNote, sourceOut, type Table } from '@/lib/svc-articles';
import { svcError, svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const denied = svcGuard(req); if (denied) return denied;
  const { slug } = await params;
  const url = new URL(req.url);
  const lang = svcLang(url);
  const a = SLUG.test(slug) ? getArticle(slug) : undefined;
  if (!a) return svcError(404, 'unknown-article', 'Unknown article', `${slug.slice(0, 100)} is not the slug of a published datasteg article. The articles view lists them (slugs such as won-after-rate-hold).`);
  const chart = url.searchParams.get('chart') || '';
  if (chart && !a.charts[chart]) return svcError(404, 'unknown-chart', 'Unknown chart', `${chart.slice(0, 100)} is not a chart of ${a.slug}. Its charts: ${(a.meta.charts ?? []).join(', ')}.`);
  const limit = intParam(url, 'limit', 25, 1, 100);
  if (typeof limit === 'string') return svcError(400, 'bad-parameter', 'Bad limit', limit);
  const from = intParam(url, 'cursor', 0, 0, 100000);
  if (typeof from === 'string') return svcError(400, 'bad-parameter', 'Bad cursor', 'cursor is the value a previous answer returned; leave it out for the first page.');
  const all = publishedFacts(a);
  const facts = all.slice(from, from + limit).map(factOut);
  const next = from + limit < all.length ? String(from + limit) : null;
  const c = chart ? chartOut(a, chart, lang) : null;
  const table: Table = chart ? chartTable(a.charts[chart], lang) : {
    columns: [{ id: 'id', label: 'Fact' }, { id: 'value', label: 'Value' }, { id: 'unit', label: 'Unit' }, { id: 'period', label: 'Period' }, { id: 'sources', label: 'Sources' }],
    rows: facts.map((f) => [f.id, f.value, f.unit, f.period, f.sources.join(' ')]),
  };
  const used = new Set([...facts.flatMap((f) => f.sources), ...(c?.meta.sources ?? [])]);
  const chartSources = new Set(c?.meta.sources ?? []);
  const title = listItem(a, 'en').title;
  const unmarked = (a.meta.facts ?? []).some((f) => f.publishable === undefined);
  const en = chart ? chartOut(a, chart, 'en') : null;
  return svcJson(envelope('facts', lang, {
    page: pageOf(a, lang) + (chart ? `#fig-${chart}` : ''),
    summary: `“${title}” (datasteg articles, ${a.meta.date}): ${all.length} published facts${facts.length ? `, ${facts[0].id} to ${facts[facts.length - 1].id} listed here` : ''}.`
      + (en ? ` Chart ${chart}: “${en.title ?? en.headline ?? chart}”, ${table.rows.length} rows${en.meta.provider ? ` from ${en.meta.provider}` : ''}${en.meta.last_observation ? `, data to ${en.meta.last_observation}` : ''}.` : ''),
    data: { slug: a.slug, count: all.length, offset: from, facts, ...(c ? { chart: c } : {}) },
    sources: a.sources.filter((x) => used.has(x.id)).map((x) => sourceOut(x, lang, { locate: chartSources.has(x.id) })),
    table, cursor: next,
    notes: [
      reuseNote(lang),
      'Facts are the article\'s numbers as its analysis computed them, before rounding; the text shows them rounded. Only published facts are listed: numbers the pipeline blocked are left out, and so are the ids between them.',
      'sources names the sources.json ids each fact was computed from; a fact none of whose series the article cites names them in series instead.',
      ...(chart ? ['table holds the chart\'s data, the same rows as the CSV the page offers (data.chart.csv), with labels in the asked language.'] : []),
      ...(unmarked ? ['Some of this article\'s facts are not yet marked for the API and are left out.'] : []),
    ],
  }));
}
