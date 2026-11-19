// GET /svc/v1/articles?topic=&country=&type=&limit=&cursor=&lang=: the articles, newest first, as the home page lists
// them (and filters them by topic), with each one's countries and type.
import { ARTICLES, TOPICS } from '@/lib/content';
import { economy } from '@/lib/svc-economies';
import { ARTICLE_TYPES, envelope, intParam, listItem, type Table } from '@/lib/svc-articles';
import { svcError, svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const denied = svcGuard(req); if (denied) return denied;
  const url = new URL(req.url);
  const lang = svcLang(url);
  const topic = url.searchParams.get('topic') || '';
  const type = url.searchParams.get('type') || '';
  const country = (url.searchParams.get('country') || '').toUpperCase();
  if (topic && !TOPICS.some((t) => t.id === topic)) return svcError(400, 'bad-parameter', 'Unknown topic', `topic must be one of: ${TOPICS.map((t) => t.id).join(', ')}. The topics view lists them with their labels.`);
  if (type && !ARTICLE_TYPES.includes(type)) return svcError(400, 'bad-parameter', 'Unknown article type', `type must be one of: ${ARTICLE_TYPES.join(', ')}.`);
  let iso2 = '';
  if (country) {
    if (/^[A-Z]{2}$/.test(country)) iso2 = country;
    else if (/^[A-Z0-9]{3,4}$/.test(country) && economy(country)) iso2 = economy(country)!.iso2;
    else return svcError(400, 'bad-parameter', 'Unknown country code', `country is an ISO 3166-1 code, alpha-2 (KR) or alpha-3 (KOR); EA or EMU for the euro area, EU for the European Union. Got "${country.slice(0, 20)}".`);
  }
  const limit = intParam(url, 'limit', 25, 1, 100);
  if (typeof limit === 'string') return svcError(400, 'bad-parameter', 'Bad limit', limit);
  const from = intParam(url, 'cursor', 0, 0, 100000);
  if (typeof from === 'string') return svcError(400, 'bad-parameter', 'Bad cursor', 'cursor is the value a previous answer returned; leave it out for the first page.');
  const all = ARTICLES.filter((a) => (!topic || a.meta.topics.some((t) => t.id === topic)) && (!type || (a.meta.type ?? 'explainer') === type) && (!iso2 || (a.meta.countries ?? []).includes(iso2)));
  const items = all.slice(from, from + limit).map((a) => listItem(a, lang));
  const next = from + limit < all.length ? String(from + limit) : null;
  const filters = [topic && `topic ${topic}`, type && `type ${type}`, iso2 && `country ${iso2}`].filter(Boolean).join(', ');
  const en = all.slice(0, 3).map((a) => `“${listItem(a, 'en').title}” (${a.meta.date})`).join('; ');
  const table: Table = {
    columns: [{ id: 'slug', label: 'Slug' }, { id: 'date', label: 'Date' }, { id: 'updated', label: 'Updated' }, { id: 'type', label: 'Type' }, { id: 'title', label: 'Title' },
      { id: 'kicker', label: 'Kicker' }, { id: 'topics', label: 'Topics' }, { id: 'countries', label: 'Countries' }, { id: 'page', label: 'Page' }],
    rows: items.map((x) => [x.slug, x.date, x.updated, x.type, x.title, x.kicker, x.topics.map((t) => t.id).join(' '), x.countries.join(' '), x.page]),
  };
  return svcJson(envelope('articles', lang, {
    page: topic ? `/${lang}?topic=${topic}` : `/${lang}`,
    summary: all.length
      ? `${all.length} datasteg article${all.length === 1 ? '' : 's'}${filters ? ` (${filters})` : ''}, newest first: ${en}${all.length > 3 ? '; …' : ''}.`
      : `No datasteg article matches ${filters}.`,
    data: { count: all.length, offset: from, articles: items },
    table, cursor: next,
  }));
}
