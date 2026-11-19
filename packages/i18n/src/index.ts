import en from '../messages/en.json';
import ko from '../messages/ko.json';

export type Lang = 'en' | 'ko';
export const LANGS: Lang[] = ['en', 'ko'];
export const DEFAULT_LANG: Lang = 'en';
export const LANG_COOKIE = 'glacier-lang';
export type MessageKey = keyof typeof en;

const MESSAGES: Record<Lang, Record<MessageKey, string>> = { en, ko: ko as Record<MessageKey, string> };
const LOCALE: Record<Lang, string> = { en: 'en-GB', ko: 'ko-KR' };

export function isLang(v: unknown): v is Lang {
  return v === 'en' || v === 'ko';
}

/** Interface string for `key`, with `{n}`-style placeholders filled from `vars`. */
export function t(lang: Lang, key: MessageKey, vars?: Record<string, string | number>): string {
  const s = MESSAGES[lang][key] ?? MESSAGES.en[key] ?? key;
  return vars ? s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? '')) : s;
}

/** A leading "-" (and one after a space) becomes a true minus "−". */
export function minus(s: string | number): string {
  return String(s).replace(/^-/, '−').replace(/(\s)-/g, '$1−');
}

export function formatNumber(
  v: number | null | undefined,
  o: { lang?: Lang; decimals?: number; compact?: boolean; signed?: boolean; unit?: string } = {},
): string {
  if (v == null || Number.isNaN(v)) return '–';
  const opts: Intl.NumberFormatOptions = {
    maximumFractionDigits: o.decimals ?? 1,
    minimumFractionDigits: o.decimals ?? 0,
  };
  if (o.compact) opts.notation = 'compact';
  if (o.signed) opts.signDisplay = 'exceptZero';
  return minus(new Intl.NumberFormat(LOCALE[o.lang ?? 'en'], opts).format(v)) + (o.unit ?? '');
}

/** byline "14 Oct 2026" / "2026년 10월 14일"; feed "14 Oct" / "10월 14일"; month "Oct 2026" / "2026년 10월". */
export function formatDate(d: Date | string, o: { lang?: Lang; style?: 'byline' | 'feed' | 'month' } = {}): string {
  const date = d instanceof Date ? d : new Date(d);
  const lang = o.lang ?? 'en';
  const month = lang === 'ko' ? 'long' : 'short';
  const style = o.style ?? 'byline';
  const opt: Intl.DateTimeFormatOptions =
    style === 'feed' ? { day: 'numeric', month }
    : style === 'month' ? { year: 'numeric', month }
    : { day: 'numeric', month, year: 'numeric' };
  return new Intl.DateTimeFormat(LOCALE[lang], { ...opt, timeZone: 'UTC' }).format(date);
}
