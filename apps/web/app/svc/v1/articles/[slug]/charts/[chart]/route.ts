// GET /svc/v1/articles/{slug}/charts/{chart}?lang=: one chart's data as `table` (the rows of the CSV the page offers,
// /data/<slug>/<chart>.csv; the api service serves it as CSV too) with its titles and metadata.
import { getArticle } from '@/lib/content';
import { SLUG, chartOut, chartTable, envelope, listItem, pageOf, reuseNote, sourceOut } from '@/lib/svc-articles';
import { svcError, svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: Promise<{ slug: string; chart: string }> }) {
  const denied = svcGuard(req); if (denied) return denied;
  const { slug, chart } = await params;
  const lang = svcLang(new URL(req.url));
  const a = SLUG.test(slug) ? getArticle(slug) : undefined;
  if (!a) return svcError(404, 'unknown-article', 'Unknown article', `${slug.slice(0, 100)} is not the slug of a published datasteg article. The articles view lists them (slugs such as won-after-rate-hold).`);
  if (!a.charts[chart]) return svcError(404, 'unknown-chart', 'Unknown chart', `${chart.slice(0, 100)} is not a chart of ${a.slug}. Its charts: ${(a.meta.charts ?? []).join(', ')}.`);
  const c = chartOut(a, chart, lang);
  const en = chartOut(a, chart, 'en');
  const table = chartTable(a.charts[chart], lang);
  const ids = new Set(c.meta.sources);
  return svcJson(envelope('chart', lang, {
    page: pageOf(a, lang) + `#fig-${chart}`,
    summary: `Chart ${chart} of “${listItem(a, 'en').title}” (datasteg articles, ${a.meta.date}): ${en.title ?? en.headline ?? chart}. ${table.rows.length} rows`
      + `${en.meta.provider ? ` from ${en.meta.provider}` : ''}${en.meta.last_observation ? `, data to ${en.meta.last_observation}` : ''}.${en.headline ? ` ${en.headline}` : ''}`,
    data: { slug: a.slug, chart: c },
    sources: a.sources.filter((x) => ids.has(x.id)).map((x) => sourceOut(x, lang, { locate: true })),
    table,
    notes: [reuseNote(lang), 'table holds the chart\'s data, the same rows as the CSV the page offers (data.chart.csv), with labels in the asked language.'],
  }));
}
