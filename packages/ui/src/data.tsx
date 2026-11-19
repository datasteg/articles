import { minus, t, type Lang } from '@glacier/i18n';
import { cx, seriesColor, type SeriesColor } from './util';

const ARROW = { up: 'M6 1.5 11 9H1z', down: 'M6 10.5 1 3h10z', flat: 'M1 6h8M7 3l3 3-3 3' };

export interface DeltaProps {
  lang: Lang;
  /** Signed, formatted: "+0.2 pp", "-8bp" (a leading "-" becomes "−"). */
  value: string;
  direction?: 'up' | 'down' | 'flat';
  /** good/bad/neutral for indicators; rise/fall for market prices (flips inside [data-market="kr"]). */
  tone?: 'good' | 'bad' | 'neutral' | 'rise' | 'fall';
  className?: string;
}
export function Delta(p: DeltaProps) {
  const dir = p.direction ?? 'flat';
  const tone = p.tone ?? 'neutral';
  return (
    <span className={cx('gl-delta', 'gl-delta--' + tone, p.className)}>
      <svg viewBox="0 0 12 12" className="gl-delta__arrow" aria-hidden focusable="false">
        {dir === 'flat'
          ? <path d={ARROW.flat} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
          : <path d={ARROW[dir]} fill="currentColor" />}
      </svg>
      <span className="gl-visually-hidden">{t(p.lang, dir) + ' '}</span>
      <span>{minus(p.value)}</span>
    </span>
  );
}

export function Sparkline(p: { data: number[]; width?: number; height?: number; label?: string; className?: string }) {
  const data = p.data.filter((v) => v != null);
  const w = p.width ?? 112, hgt = p.height ?? 32, pad = 4;
  if (data.length < 2) return null;
  const min = Math.min(...data), max = Math.max(...data), span = max - min || 1;
  const x = (i: number) => pad + (i * (w - 2 * pad)) / (data.length - 1);
  const y = (v: number) => hgt - pad - ((v - min) / span) * (hgt - 2 * pad);
  const d = data.map((v, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1)).join(' ');
  return (
    <svg className={cx('gl-spark', p.className)} width={w} height={hgt} viewBox={`0 0 ${w} ${hgt}`} role={p.label ? 'img' : undefined} aria-label={p.label} aria-hidden={p.label ? undefined : true}>
      <path d={d} className="gl-spark__line" />
      <circle cx={x(data.length - 1)} cy={y(data[data.length - 1])} r={3} className="gl-spark__dot" />
    </svg>
  );
}

export function StatTile(p: {
  lang: Lang; label: string; value: string; unit?: string; delta?: Omit<DeltaProps, 'lang'>; period?: string;
  trend?: number[]; trendLabel?: string; source?: string; hero?: boolean; className?: string;
}) {
  return (
    <div className={cx('gl-stat', p.hero && 'gl-stat--hero', p.className)} lang={p.lang}>
      <p className="gl-stat__label">{p.label}</p>
      <p className="gl-stat__value">{minus(p.value)}{p.unit ? <span className="gl-stat__unit">{p.unit}</span> : null}</p>
      {p.delta || p.period ? (
        <p className="gl-stat__delta">
          {p.delta ? <Delta lang={p.lang} {...p.delta} /> : null}
          {p.period ? <span className="gl-stat__period">{p.period}</span> : null}
        </p>
      ) : null}
      {p.trend ? <div className="gl-stat__trend"><Sparkline data={p.trend} width={p.hero ? 200 : 112} height={p.hero ? 40 : 32} label={p.trendLabel} /></div> : null}
      {p.source ? <p className="gl-stat__source">{p.source}</p> : null}
    </div>
  );
}

export interface TooltipRow { label: string; value: string; color?: SeriesColor; type?: 'line' | 'bar' }
export function ChartTooltip(p: { title?: string; rows: TooltipRow[]; style?: React.CSSProperties; className?: string }) {
  return (
    <div className={cx('gl-tip', p.className)} role="presentation" style={p.style}>
      {p.title ? <p className="gl-tip__title">{p.title}</p> : null}
      {p.rows.map((r, i) => (
        <p key={i} className="gl-tip__row">
          <span className={cx('gl-tip__key', r.type === 'bar' && 'gl-tip__key--bar')} style={{ background: seriesColor(r.color) }} aria-hidden />
          <span className="gl-tip__value">{r.value}</span>
          <span className="gl-tip__label">{r.label}</span>
        </p>
      ))}
    </div>
  );
}
