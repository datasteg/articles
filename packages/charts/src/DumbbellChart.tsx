'use client';
import { useRef, useState } from 'react';
import { ChartTooltip } from '@glacier/ui';
import type { Lang } from '@glacier/i18n';
import { useWidth } from './hooks';
import { decimalsOf, fmt, textWidth, valueAxis } from './scale';
import { tx, type ChartSpec } from './types';

/** Then versus now, by item: a hollow dot (from), a filled dot (to), joined; the subject in focus colour. */
export function DumbbellChart({ spec, lang }: { spec: ChartSpec; lang: Lang }) {
  const ref = useRef<HTMLDivElement>(null);
  const { width: w, ready } = useWidth(ref, 680);
  const [hover, setHover] = useState<number | null>(null);
  const rows = spec.rows ?? [];
  const axis = spec.axes?.x;
  const dec = decimalsOf(axis, 1);
  const { lo, hi, ticks } = valueAxis(axis, rows.flatMap((r) => [r.from, r.to]));
  const label = tx(axis?.label, lang);
  const anyHighlight = rows.some((r) => r.highlight);
  const rowH = 36;
  const narrow = w < 520;
  const labelW = Math.min(w * 0.3, Math.max(...rows.map((r) => textWidth(tx(r.label, lang), 13))) + 14);
  const m = { t: 8, l: labelW, r: narrow ? 40 : 52, b: 22 + (label ? 20 : 0) };
  const pw = Math.max(60, w - m.l - m.r);
  const X = (v: number) => m.l + ((v - lo) / (hi - lo || 1)) * pw;
  const plotH = rows.length * rowH;
  const height = m.t + plotH + m.b;
  const fromLabel = tx(spec.fromLabel, lang), toLabel = tx(spec.toLabel, lang);
  const col = (h?: boolean) => (anyHighlight ? (h ? 'var(--viz-focus)' : 'var(--viz-context)') : 'var(--viz-1)');
  const tip = hover != null ? rows[hover] : null;

  return (
    <div className="ac-chart ac-dumbbell">
      <div className="ac-chart__legend">
        <ul className="gl-legend" aria-hidden>
          <li><span className="gl-legend__item"><span className="ac-key ac-key--from" />{fromLabel}</span></li>
          <li><span className="gl-legend__item"><span className="ac-key ac-key--to" />{toLabel}</span></li>
        </ul>
      </div>
      <div ref={ref} className="gl-chart" data-ready={ready ? '1' : undefined}>
        <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`} role="img" aria-label={tx(spec.alt, lang)}>
          {rows.map((r, i) => {
            const y = m.t + i * rowH + rowH / 2;
            const xf = X(r.from), xt = X(r.to);
            const name = tx(r.label, lang);
            const c = col(r.highlight);
            const rising = r.to >= r.from;
            const vFrom = fmt(r.from, lang, { decimals: dec }), vTo = fmt(r.to, lang, { decimals: dec });
            // value labels sit outside the dumbbell; one that would run into the row labels moves to the right end.
            // Phones show only the latest value (the from value stays in the tooltip and the table).
            // overlapping dots: the from dot is drawn over the filled one; where they all but coincide it becomes
            // a wider ring around it, so both show
            const gap = Math.abs(xt - xf);
            const over = gap < 11, ring = gap < 4;
            const pad = ring ? 14 : 10;
            const wTo = textWidth(vTo, 12), wFrom = textWidth(vFrom, 12);
            const hi = Math.max(xf, xt), lo = Math.min(xf, xt);
            const toLeftFits = lo - pad - wTo >= m.l;
            const toPos = rising ? { x: xt + pad, a: 'start' as const } : toLeftFits ? { x: xt - pad, a: 'end' as const } : { x: hi + pad, a: 'start' as const };
            const fromLeftFits = lo - pad - wFrom >= m.l;
            const fromPos = narrow ? null : !rising ? { x: xf + pad, a: 'start' as const }
              : fromLeftFits ? { x: xf - pad, a: 'end' as const } : { x: hi + 18 + wTo, a: 'start' as const };
            return (
              <g key={r.id} className={'gl-bar' + (hover === i ? ' is-hover' : '')} tabIndex={0}
                aria-label={`${name}: ${fromLabel} ${vFrom}, ${toLabel} ${vTo}`}
                onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}>
                <rect x={0} y={y - rowH / 2} width={w} height={rowH} fill="transparent" />
                <text x={m.l - 10} y={y + 4} textAnchor="end" className={'gl-chart__cat' + (r.highlight ? ' is-focus' : '')}>{name}</text>
                <line x1={m.l} x2={m.l + pw} y1={y} y2={y} className="ac-row-rule" />
                <line x1={xf} x2={xt} y1={y} y2={y} style={{ stroke: c }} className="ac-dumbbell__bar" />
                {over ? null : <circle cx={xf} cy={y} r={5} className="ac-dumbbell__from" style={{ stroke: c }} />}
                <circle cx={xt} cy={y} r={5.5} className="gl-chart__dot" style={{ fill: c }} />
                {over ? <circle cx={xf} cy={y} r={ring ? 9 : 5} className={'ac-dumbbell__from' + (ring ? ' is-ring' : '')} style={{ stroke: c }} /> : null}
                <text x={toPos.x} y={y + 4} textAnchor={toPos.a} className={'gl-chart__value' + (r.highlight ? ' is-focus' : '')}>{vTo}</text>
                {fromPos ? <text x={fromPos.x} y={y + 4} textAnchor={fromPos.a} className="gl-chart__tick">{vFrom}</text> : null}
              </g>
            );
          })}
          <line x1={m.l} x2={m.l + pw} y1={m.t + plotH} y2={m.t + plotH} className="ac-axis-line" />
          {ticks.filter((t) => t >= lo && t <= hi).map((t) => (
            <g key={'t' + t}>
              <line x1={X(t)} x2={X(t)} y1={m.t + plotH} y2={m.t + plotH + 4} className="ac-axis-line" />
              <text x={X(t)} y={m.t + plotH + 17} textAnchor="middle" className="gl-chart__tick">{fmt(t, lang, { decimals: 0 })}</text>
            </g>
          ))}
          {label ? <text x={m.l + pw / 2} y={height - 4} textAnchor="middle" className="ac-axis-label ac-axis-label--x">{label}</text> : null}
        </svg>
        {tip ? (
          <ChartTooltip title={tx(tip.label, lang)}
            rows={[{ label: fromLabel, value: fmt(tip.from, lang, { decimals: dec }), color: 'context' }, { label: toLabel, value: fmt(tip.to, lang, { decimals: dec }), color: tip.highlight ? 'focus' : 'context' }]}
            style={{ left: Math.min(Math.max(X(tip.from), X(tip.to)) + 16, w - 170) + 'px', top: m.t + (hover as number) * rowH + 'px' }} />
        ) : null}
      </div>
    </div>
  );
}
