import type { ReactNode } from 'react';
import type { Lang } from '@glacier/i18n';

export type { Lang };
/** A categorical slot 1–8, the emphasis colour, the de-emphasis grey, or a raw `var(--token)`. */
export type SeriesColor = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 'focus' | 'context' | (string & {});

export function cx(...a: Array<string | false | null | undefined>): string {
  return a.filter(Boolean).join(' ');
}
export function pad2(n: number): string {
  return n < 10 ? '0' + n : String(n);
}
export function seriesColor(c?: SeriesColor): string {
  if (c === 'focus') return 'var(--viz-focus)';
  if (c === 'context') return 'var(--viz-context)';
  if (typeof c === 'string' && c.startsWith('var(')) return c;
  return 'var(--viz-' + (c || 1) + ')';
}
export function initials(name: string): string {
  const s = String(name || '').trim();
  if (/[가-힣]/.test(s)) return s.replace(/\s+/g, '').slice(0, 2);
  return s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join('');
}

/* ---------- icons (Lucide-style, 1.5px stroke) ---------- */
export const ICONS = {
  bookmark: ['M6 3.5h12v17l-6-4-6 4z'],
  share: ['M12 15V3.5', 'M7.5 8 12 3.5 16.5 8', 'M5 12.5v7h14v-7'],
  unlock: ['M5 11h14v9.5H5z', 'M8 11V7.5a4 4 0 0 1 7.6-1.7'],
  download: ['M12 4v11', 'M7.5 10.5 12 15l4.5-4.5', 'M5 19.5h14'],
  chevron: ['M6 9l6 6 6-6'],
  info: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 11v5', 'M12 7.6v.1'],
  good: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M8 12.2l2.7 2.7L16 9.6'],
  warning: ['M10.3 4.2 2.6 17.6A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-2.9L13.7 4.2a2 2 0 0 0-3.4 0z', 'M12 9.5v4', 'M12 17v.1'],
  critical: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M9 9l6 6', 'M15 9l-6 6'],
  globe: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M3 12h18', 'M12 3c2.5 2.7 3.6 5.7 3.6 9s-1.1 6.3-3.6 9c-2.5-2.7-3.6-5.7-3.6-9S9.5 5.7 12 3z'],
  sort: ['M8 9l4-4 4 4', 'M8 15l4 4 4-4'],
} as const;
export type IconName = keyof typeof ICONS;

export function Icon({ name }: { name: IconName }): ReactNode {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden focusable="false">
      {ICONS[name].map((d, i) => <path key={i} d={d} />)}
    </svg>
  );
}

/* ---------- decorative strata ---------- */
const STRATA: Array<[number, number, number, number?]> = [
  [28, 120, 480], [44, 200, 480], [58, 80, 480, 1], [86, 260, 480], [100, 150, 480],
  [128, 40, 480], [140, 300, 480, 1], [168, 180, 480], [190, 100, 480], [204, 340, 480],
  [232, 220, 480], [250, 60, 480, 1], [272, 280, 480], [296, 140, 480],
];
export function StrataArt(): ReactNode {
  return (
    <svg className="gl-strata-art" viewBox="0 0 480 320" preserveAspectRatio="xMaxYMid slice" aria-hidden focusable="false">
      {STRATA.map((s, i) => <line key={i} x1={s[1]} y1={s[0]} x2={s[2]} y2={s[0]} className={s[3] ? 'is-melt' : undefined} />)}
    </svg>
  );
}
