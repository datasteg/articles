// How readers cite an article: meta.citation (stamped by `artools publish` from config/editorial.yaml) as one line
// and as a biblatex entry, in the edition's language (contracts/content.md § Citation).
import type { Lang } from '@glacier/i18n';
import { tx } from '@articles/charts';
import type { Citation } from '@/lib/content';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** "21 October 2026", "2026년 10월 21일". */
function longDate(iso: string, lang: Lang): string {
  const [y, m, d] = iso.split('-').map(Number);
  if (!m) return String(y);
  return lang === 'ko' ? `${y}년 ${m}월${d ? ` ${d}일` : ''}` : `${d ? `${d} ` : ''}${MONTHS[m - 1]} ${y}`;
}

/** Author (year), “title”, publisher, date, URL. */
export function citationText(c: Citation, lang: Lang): string {
  const title = tx(c.title, lang);
  return `${tx(c.author, lang)} (${c.date.slice(0, 4)}), ${lang === 'ko' ? `「${title}」` : `“${title}”`}, ${tx(c.publisher, lang)}, ${longDate(c.date, lang)}, ${tx(c.url, lang)}.`;
}

const tex = (x: string) => x.replace(/[\\{}]/g, '').replace(/([&%$#_])/g, '\\$1');

/** A biblatex @online entry. An organisation's name ("datasteg") is braced so it isn't split into first and last names;
 *  a person's ("Doe, Jane") is not. */
export function citationBibtex(c: Citation, slug: string, lang: Lang): string {
  const author = tex(tx(c.author, lang));
  const fields: Array<[string, string]> = [
    ['author', author.includes(',') ? author : `{${author}}`],
    ['title', tex(tx(c.title, lang))],
    ['organization', tex(tx(c.publisher, lang))],
    ['date', c.date],
    ['url', tx(c.url, lang)],
    ...(lang === 'ko' ? [['langid', 'korean'] as [string, string]] : []),
  ];
  return `@online{datasteg:${slug},\n${fields.map(([k, v]) => `  ${k.padEnd(12)} = {${v}}`).join(',\n')}\n}`;
}
