import { formatNumber, type Lang } from '@glacier/i18n';
import type { Axis, NumberFormat, SeriesColor } from './types';

/** Round tick values covering [min, max], about `count` steps (Glacier: 4–6 clean values). */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (min === max) { min -= 1; max += 1; }
  const raw = (max - min) / count, mag = Math.pow(10, Math.floor(Math.log10(raw))), err = raw / mag;
  const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
  const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, out: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) out.push(+v.toFixed(10));
  return out;
}

/** Domain and ticks of a value axis: as given by the chart file, else nice ticks around the data. */
export function valueAxis(axis: Axis | undefined, values: number[], opts: { zero?: boolean } = {}): { lo: number; hi: number; ticks: number[] } {
  const given = axis?.ticks?.filter((t): t is number => typeof t === 'number');
  if (axis?.domain) {
    const [lo, hi] = axis.domain;
    return { lo, hi, ticks: given?.length ? given : niceTicks(lo, hi, 4).filter((t) => t >= lo && t <= hi) };
  }
  const vs = values.filter((v) => Number.isFinite(v));
  if (opts.zero) vs.push(0);
  const ticks = given?.length ? given : niceTicks(Math.min(...vs), Math.max(...vs), 4);
  return { lo: Math.min(ticks[0], ...vs), hi: Math.max(ticks[ticks.length - 1], ...vs), ticks };
}

export function decimalsOf(axis?: Axis, fallback = 0): number {
  const f = axis?.format;
  return f && typeof f === 'object' && f.decimals != null ? f.decimals : fallback;
}

export function fmt(v: number | null | undefined, lang: Lang, f: NumberFormat = {}): string {
  if (v == null || Number.isNaN(v)) return '–';
  return (f.prefix ?? '') + formatNumber(v, { lang, decimals: f.decimals ?? 1 }) + (f.suffix ?? '');
}

const MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-09" → "Sep 2026" / "2026년 9월"; "2026-09-14" → "14 Sep 2026" / "2026년 9월 14일"; "2026-Q2" → "Q2 2026" /
 *  "2026년 2분기"; style "year" → "2026". */
export function fmtPeriod(s: string, lang: Lang, style: 'year' | 'month' | 'auto' = 'auto'): string {
  const m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/.exec(s);
  if (!m) {
    const q = /^(\d{4})-?Q([1-4])$/.exec(s);
    if (q && style === 'year') return q[1];
    if (q) return lang === 'ko' ? `${q[1]}년 ${q[2]}분기` : `Q${q[2]} ${q[1]}`;
    return s;
  }
  const [, y, mo, d] = m;
  if (style === 'year' || !mo) return lang === 'ko' && style !== 'year' ? `${y}년` : y;
  const mi = Number(mo);
  if (d && style === 'auto') return lang === 'ko' ? `${y}년 ${mi}월 ${Number(d)}일` : `${Number(d)} ${MONTHS_EN[mi - 1]} ${y}`;
  return lang === 'ko' ? `${y}년 ${mi}월` : `${MONTHS_EN[mi - 1]} ${y}`;
}

export function colorOf(c?: SeriesColor | string): string {
  if (c === 'focus') return 'var(--viz-focus)';
  if (c === 'context') return 'var(--viz-context)';
  if (typeof c === 'number') return `var(--viz-${c})`;
  return 'var(--viz-1)';
}

/** Rough text width for layout before the browser measures (Hanken Grotesk ≈ 0.56em; Hangul ≈ 0.95em). */
export function textWidth(s: string, size = 12): number {
  let w = 0;
  for (const ch of s) w += /[ㄱ-힝]/.test(ch) ? 0.95 : /[A-Z0-9%]/.test(ch) ? 0.62 : 0.54;
  return w * size;
}
