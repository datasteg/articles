import type { Lang } from '@glacier/i18n';
import { tx } from '@articles/charts';
import type { GlossaryTerm } from './content';

const CHO = ['ㄱ', 'ㄱ', 'ㄴ', 'ㄷ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅂ', 'ㅅ', 'ㅅ', 'ㅇ', 'ㅈ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];
const ORDER_KO = ['ㄱ', 'ㄴ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅅ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];

/** The index letter of a term: A–Z, or for Korean the initial consonant with doubled ones under their base
 *  (ㄲ under ㄱ); anything else under "#". */
export function initialOf(term: string): string {
  const c = term.trim().charAt(0);
  const code = c.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) return CHO[Math.floor((code - 0xac00) / 588)];
  if (/[a-z]/i.test(c)) return c.toUpperCase();
  return '#';
}

const collator = (lang: Lang) => new Intl.Collator(lang === 'ko' ? 'ko-KR' : 'en-GB', { sensitivity: 'base', numeric: true });

/** Terms in letter groups, in dictionary order: ㄱ–ㅎ then A–Z in Korean, A–Z in English; "#" last. */
export function byInitial(terms: GlossaryTerm[], lang: Lang): Array<{ letter: string; terms: GlossaryTerm[] }> {
  const cmp = collator(lang);
  const groups = new Map<string, GlossaryTerm[]>();
  for (const g of [...terms].sort((a, b) => cmp.compare(tx(a.term, lang), tx(b.term, lang)))) {
    const k = initialOf(tx(g.term, lang));
    groups.set(k, [...(groups.get(k) ?? []), g]);
  }
  const rank = (k: string) => (k === '#' ? 1000 : ORDER_KO.includes(k) ? ORDER_KO.indexOf(k) : 100 + k.charCodeAt(0));
  return [...groups.entries()].sort((a, b) => rank(a[0]) - rank(b[0])).map(([letter, list]) => ({ letter, terms: list }));
}

export const sortTerms = (terms: GlossaryTerm[], lang: Lang) => [...terms].sort((a, b) => collator(lang).compare(tx(a.term, lang), tx(b.term, lang)));
