// GET /svc/v1/economy/{iso3}?lang=: the articles that cover one economy (meta.countries, ISO 3166-1 alpha-2 plus EA
// for the euro area and EU), newest first, for the cross-app economy profile. An economy no article covers answers
// covered: false.
import { ARTICLES } from '@/lib/content';
import { economy } from '@/lib/svc-economies';
import { envelope, listItem } from '@/lib/svc-articles';
import { svcError, svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: Promise<{ iso3: string }> }) {
  const denied = svcGuard(req); if (denied) return denied;
  const { iso3 } = await params;
  const lang = svcLang(new URL(req.url));
  const code = iso3.toUpperCase();
  if (!/^[A-Z0-9]{2,5}$/.test(code)) return svcError(400, 'bad-parameter', 'Bad economy code', `Use an ISO 3166-1 alpha-3 code such as KOR (EMU for the euro area, EUU for the European Union); got "${iso3.slice(0, 20)}".`);
  const e = economy(code);
  const list = e ? ARTICLES.filter((a) => (a.meta.countries ?? []).includes(e.iso2)) : [];
  const items = list.map((a) => listItem(a, lang));
  const en = list.map((a) => listItem(a, 'en'));
  const name = e?.name ?? null;
  return svcJson(envelope('economy', lang, {
    page: `/${lang}`,
    summary: list.length
      ? `${list.length} datasteg article${list.length === 1 ? '' : 's'} cover${list.length === 1 ? 's' : ''} ${name} (${e!.iso2}), newest first: ${en.slice(0, 3).map((x) => `“${x.title}” (${x.date})`).join('; ')}${list.length > 3 ? '; …' : ''}.`
      : `No datasteg article covers ${name ?? code}${e ? ` (${e.iso2})` : ''}.`,
    data: {
      covered: list.length > 0, code: e?.iso3 ?? code, iso2: e?.iso2 ?? null, name, count: list.length,
      headline: items.slice(0, 8).map((x) => ({ label: x.title, value: x.kicker, unit: null, period: x.date })),
      links: items.map((x) => ({ label: x.title, page: x.page, date: x.date, type: x.type })),
    },
  }));
}
