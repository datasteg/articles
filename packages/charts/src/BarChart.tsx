'use client';
import { useRef, useState } from 'react';
import { ChartTooltip } from '@glacier/ui';
import type { Lang } from '@glacier/i18n';
import { useWidth } from './hooks';
import { decimalsOf, fmt, textWidth, valueAxis } from './scale';
import { tx, type ChartSpec } from './types';

function barPath(x0: number, x1: number, y: number, h: number, r: number): string {
  const len = Math.abs(x1 - x0);
  r = Math.min(r, len / 2, h / 2);
  if (len < 0.5) return '';
  return `M${x0} ${y}H${x1 - r}A${r} ${r} 0 0 1 ${x1} ${y + r}V${y + h - r}A${r} ${r} 0 0 1 ${x1 - r} ${y + h}H${x0}Z`;
}

/** Compare one measure across items: horizontal bars from zero, sorted, the subject highlighted,
 *  values at the tip, an optional reference line (Glacier 04 §1, §3). */
export function BarChart({ spec, lang }: { spec: ChartSpec; lang: Lang }) {
  const ref = useRef<HTMLDivElement>(null);
  const { width: w, ready } = useWidth(ref, 680);
  const [hover, setHover] = useState<number | null>(null);
  const cats = spec.categories ?? [];
  const axis = spec.axes?.x;
  const vf = spec.valueFormat ?? { decimals: 0 };
  const refs = (spec.referenceLines ?? []).filter((r) => r.axis === 'x');
  const { hi, ticks } = valueAxis(axis, [...cats.map((c) => c.value), ...refs.map((r) => r.value)], { zero: true });
  const lo = 0; // bars always start at zero
  const label = tx(axis?.label, lang);
  const anyHighlight = cats.some((c) => c.highlight);
  const thick = 22, gap = 14;
  const labelW = Math.min(w * 0.36, Math.max(...cats.map((c) => textWidth(tx(c.label, lang), 13))) + 14);
  const valueW = Math.max(...cats.map((c) => textWidth(fmt(c.value, lang, vf), 12))) + 12;
  const top = refs.some((r) => r.label) ? 22 : 6;
  const m = { t: top, l: labelW, r: valueW + 4, b: 22 + (label ? 20 : 0) };
  const pw = Math.max(60, w - m.l - m.r);
  const X = (v: number) => m.l + ((v - lo) / (hi - lo || 1)) * pw;
  const plotH = cats.length * (thick + gap) - gap + 8;
  const height = m.t + plotH + m.b;
  const colorOf = (highlight?: boolean) => (anyHighlight ? (highlight ? 'var(--viz-focus)' : 'var(--viz-context)') : 'var(--viz-1)');
  const tipFor = hover != null ? cats[hover] : null;

  return (
    <div className="ac-chart ac-bars">
      <div ref={ref} className="gl-chart" data-ready={ready ? '1' : undefined}>
        <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`} role="img" aria-label={tx(spec.alt, lang)}>
          {refs.map((r, i) => (
            <g key={'r' + i}>
              <line x1={X(r.value)} x2={X(r.value)} y1={m.t - 4} y2={m.t + plotH} className="ac-ref" />
              {r.label ? <text x={X(r.value)} y={m.t - 8} textAnchor={X(r.value) > m.l + pw * 0.7 ? 'end' : 'middle'} className="ac-ref-label">{tx(r.label, lang)}</text> : null}
            </g>
          ))}
          {cats.map((c, i) => {
            const y = m.t + 4 + i * (thick + gap);
            const x1 = X(c.value);
            const name = tx(c.label, lang);
            return (
              <g key={c.id} className={'gl-bar' + (hover === i ? ' is-hover' : '')} tabIndex={0} aria-label={`${name}: ${fmt(c.value, lang, vf)}`}
                onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}>
                <rect x={0} y={y - gap / 2} width={w} height={thick + gap} fill="transparent" />
                <text x={m.l - 10} y={y + thick / 2 + 4} textAnchor="end" className={'gl-chart__cat' + (c.highlight ? ' is-focus' : '')}>{name}</text>
                <path d={barPath(X(0), x1, y, thick, 4)} style={{ fill: colorOf(c.highlight) }} />
                <text x={x1 + 6} y={y + thick / 2 + 4} className={'gl-chart__value' + (c.highlight ? ' is-focus' : '')}>{fmt(c.value, lang, vf)}</text>
              </g>
            );
          })}
          <line x1={X(0)} x2={X(0)} y1={m.t} y2={m.t + plotH} className="gl-chart__zero" />
          <line x1={m.l} x2={m.l + pw} y1={m.t + plotH} y2={m.t + plotH} className="ac-axis-line" />
          {ticks.filter((t) => t >= lo && t <= hi).map((t) => (
            <g key={'t' + t}>
              <line x1={X(t)} x2={X(t)} y1={m.t + plotH} y2={m.t + plotH + 4} className="ac-axis-line" />
              <text x={X(t)} y={m.t + plotH + 17} textAnchor={t === lo ? 'start' : t === hi ? 'end' : 'middle'} className="gl-chart__tick">{fmt(t, lang, { decimals: decimalsOf(axis, vf.decimals ?? 0) })}</text>
            </g>
          ))}
          {label ? <text x={m.l + pw / 2} y={height - 4} textAnchor="middle" className="ac-axis-label ac-axis-label--x">{label}</text> : null}
        </svg>
        {tipFor ? (
          <ChartTooltip rows={[{ label: tx(tipFor.label, lang), value: fmt(tipFor.value, lang, vf), color: anyHighlight ? (tipFor.highlight ? 'focus' : 'context') : 1, type: 'bar' }]}
            style={{ left: Math.min(X(tipFor.value) + 12, w - 180) + 'px', top: m.t + 4 + (hover as number) * (thick + gap) - 4 + 'px' }} />
        ) : null}
      </div>
    </div>
  );
}
