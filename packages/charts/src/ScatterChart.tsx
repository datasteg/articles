'use client';
import { useRef, useState } from 'react';
import { ChartTooltip } from '@glacier/ui';
import type { Lang } from '@glacier/i18n';
import { useWidth } from './hooks';
import { decimalsOf, fmt, textWidth, valueAxis } from './scale';
import { tx, type ChartSpec } from './types';

type Box = { x0: number; y0: number; x1: number; y1: number };
const overlaps = (a: Box, b: Box) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

/** Two measures and their relation: labelled points, focus vs context, horizontal gridlines only. */
export function ScatterChart({ spec, lang, height = 360 }: { spec: ChartSpec; lang: Lang; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const { width: w, ready } = useWidth(ref, 680);
  const [hover, setHover] = useState<number | null>(null);
  const pts = spec.points ?? [];
  const ax = spec.axes?.x, ay = spec.axes?.y;
  const xA = valueAxis(ax, pts.map((p) => p.x));
  const yA = valueAxis(ay, pts.map((p) => p.y));
  const dx = decimalsOf(ax, 1), dy = decimalsOf(ay, 0);
  const xLabel = tx(ax?.label, lang), yLabel = tx(ay?.label, lang);
  const tickW = Math.max(...yA.ticks.map((t) => textWidth(fmt(t, lang, { decimals: dy }), 12))) + 10;
  const m = { t: yLabel ? 28 : 10, r: 16, b: 26 + (xLabel ? 20 : 0), l: Math.max(28, tickW) };
  const pw = Math.max(60, w - m.l - m.r), ph = height - m.t - m.b;
  const X = (v: number) => m.l + ((v - xA.lo) / (xA.hi - xA.lo || 1)) * pw;
  const Y = (v: number) => m.t + ph - ((v - yA.lo) / (yA.hi - yA.lo || 1)) * ph;

  // place labels: right, left, above, below — the first spot that hits no other label or point
  const taken: Box[] = pts.map((p) => ({ x0: X(p.x) - 6, y0: Y(p.y) - 6, x1: X(p.x) + 6, y1: Y(p.y) + 6 }));
  const labels = [...pts.map((p, i) => ({ p, i }))].sort((a, b) => Number(b.p.group === 'focus') - Number(a.p.group === 'focus')).map(({ p, i }) => {
    const text = tx(p.label, lang);
    const tw = textWidth(text, 13), cx = X(p.x), cy = Y(p.y);
    const spots = [
      { x: cx + 10, y: cy + 4, anchor: 'start' as const, box: { x0: cx + 9, y0: cy - 8, x1: cx + 11 + tw, y1: cy + 6 } },
      { x: cx - 10, y: cy + 4, anchor: 'end' as const, box: { x0: cx - 11 - tw, y0: cy - 8, x1: cx - 9, y1: cy + 6 } },
      { x: cx, y: cy - 12, anchor: 'middle' as const, box: { x0: cx - tw / 2, y0: cy - 24, x1: cx + tw / 2, y1: cy - 10 } },
      { x: cx, y: cy + 22, anchor: 'middle' as const, box: { x0: cx - tw / 2, y0: cy + 10, x1: cx + tw / 2, y1: cy + 24 } },
    ];
    const inside = (b: Box) => b.x0 >= 0 && b.x1 <= w && b.y0 >= 0 && b.y1 <= height;
    const spot = spots.find((s) => inside(s.box) && taken.every((t, j) => j === i || !overlaps(s.box, t))) ?? spots[0];
    taken.push(spot.box);
    return { i, text, ...spot };
  });
  const tip = hover != null ? pts[hover] : null;

  return (
    <div className="ac-chart ac-scatter">
      <div ref={ref} className="gl-chart" data-ready={ready ? '1' : undefined} style={{ height: height + 'px' }}>
        <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`} role="img" aria-label={tx(spec.alt, lang)}>
          {yLabel ? <text x={0} y={13} className="ac-axis-label">{yLabel}</text> : null}
          {yA.ticks.map((t) => (
            <g key={'y' + t}>
              <line x1={m.l} x2={m.l + pw} y1={Y(t)} y2={Y(t)} className={t === 0 ? 'gl-chart__zero' : 'gl-chart__grid'} />
              <text x={m.l - 8} y={Y(t) + 4} textAnchor="end" className="gl-chart__tick">{fmt(t, lang, { decimals: dy })}</text>
            </g>
          ))}
          {xA.ticks.filter((t) => t >= xA.lo && t <= xA.hi).map((t) => (
            <g key={'x' + t}>
              <line x1={X(t)} x2={X(t)} y1={m.t + ph} y2={m.t + ph + 4} className="ac-axis-line" />
              <text x={X(t)} y={m.t + ph + 18} textAnchor="middle" className="gl-chart__tick">{fmt(t, lang, { decimals: 0 })}</text>
            </g>
          ))}
          {xLabel ? <text x={m.l + pw / 2} y={height - 4} textAnchor="middle" className="ac-axis-label ac-axis-label--x">{xLabel}</text> : null}
          {pts.map((p, i) => (
            <circle key={p.id} cx={X(p.x)} cy={Y(p.y)} r={p.group === 'focus' ? 6.5 : 5.5} className="gl-chart__dot ac-point" tabIndex={0}
              style={{ fill: p.group === 'focus' ? 'var(--viz-focus)' : 'var(--viz-context)' }}
              aria-label={`${tx(p.label, lang)}: ${fmt(p.x, lang, { decimals: dx })}, ${fmt(p.y, lang, { decimals: dy })}`}
              onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} />
          ))}
          {labels.map((l) => (
            <text key={'l' + l.i} x={l.x} y={l.y} textAnchor={l.anchor} className={'ac-point-label' + (pts[l.i].group === 'focus' ? ' is-focus' : '')}>{l.text}</text>
          ))}
        </svg>
        {tip ? (
          <ChartTooltip title={tx(tip.label, lang)}
            rows={[{ label: xLabel, value: fmt(tip.x, lang, { decimals: dx }), color: tip.group === 'focus' ? 'focus' : 'context' },
                   { label: yLabel, value: fmt(tip.y, lang, { decimals: dy }), color: tip.group === 'focus' ? 'focus' : 'context' }]}
            style={X(tip.x) > w * 0.6 ? { right: w - X(tip.x) + 14 + 'px', top: Math.max(0, Y(tip.y) - 20) + 'px' } : { left: X(tip.x) + 14 + 'px', top: Math.max(0, Y(tip.y) - 20) + 'px' }} />
        ) : null}
      </div>
    </div>
  );
}
