'use client';
import { useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react';
import { ChartTooltip, Legend } from '@glacier/ui';
import type { Lang } from '@glacier/i18n';
import { useWidth } from './hooks';
import { colorOf, decimalsOf, fmt, fmtPeriod, textWidth, valueAxis } from './scale';
import { tx, type ChartSpec } from './types';

/** Change over time: focus + context series, bands, ≤ 3 dated annotations, reference lines, direct end labels
 *  for the series the story is about, a legend for two or more series, crosshair tooltip (Glacier 04 §3–4). */
export function LineChart({ spec, lang, height: tall = 340 }: { spec: ChartSpec; lang: Lang; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const { width: w, ready } = useWidth(ref, 680);
  const [hidden, setHidden] = useState<string[]>([]);
  const [hover, setHover] = useState<number | null>(null);
  const xs = spec.x ?? [];
  const n = xs.length;
  const allSeries = spec.series ?? [];
  // context first so the focus line is drawn on top
  const series = [...allSeries.filter((s) => !hidden.includes(s.id))].sort((a, b) => (a.color === 'focus' ? 1 : 0) - (b.color === 'focus' ? 1 : 0));
  const yAxis = spec.axes?.y;
  const xAxis = spec.axes?.x;
  const dec = decimalsOf(yAxis, 0);
  const vals = allSeries.flatMap((s) => s.values.filter((v): v is number => v != null));
  for (const r of spec.referenceLines ?? []) if (r.axis === 'y') vals.push(r.value);
  const { lo, hi, ticks } = valueAxis(yAxis, vals);
  const yLabel = tx(yAxis?.label, lang);
  const xLabel = tx(xAxis?.label, lang);
  const annotations = (spec.annotations ?? []).slice(0, 3);
  const narrow = w < 520;
  const height = narrow ? Math.round(tall * 0.8) : tall;

  // layout: y-axis label above the plot, an annotation lane under it, end labels in the right margin
  const tickW = Math.max(...ticks.map((t) => textWidth(fmt(t, lang, { decimals: dec }), 12))) + 10;
  const m = { t: (yLabel ? 22 : 8) + (annotations.length ? 18 : 6), r: 12, b: 26 + (xLabel ? 20 : 0), l: Math.max(28, tickW) };
  const idx = (s: string) => { const i = xs.indexOf(s); if (i >= 0) return i; const j = xs.findIndex((x) => x >= s); return j < 0 ? n - 1 : j; };
  const last = (v: Array<number | null>) => { for (let i = v.length - 1; i >= 0; i--) if (v[i] != null) return i; return -1; };

  // end labels: the focus series always; others where they fit, nudged up to 10px off their dot (with a short
  // leader) when that clears a neighbour, else dropped
  const labelled = allSeries.filter((s) => s.endLabel !== false && !hidden.includes(s.id));
  const ph = height - m.t - m.b;
  const Y = (v: number) => m.t + ph - ((v - lo) / (hi - lo || 1)) * ph;
  // a label wider than the right margin may take (30% of the chart, at least 150px) wraps onto a second line; one
  // that would need three keeps only its value, so a label never runs out of the chart (t8's PDF, 17 Nov 2026: an
  // 80-character series name drawn past the plot's right edge stopped the ship)
  const cap = Math.max(150, Math.round(w * 0.3)) - 16;
  const wrap = (str: string): string[] => {
    const out: string[] = [''];
    for (const word of str.split(' ')) {
      const cur = out[out.length - 1];
      if (!cur || textWidth(cur + ' ' + word, 12) <= cap) out[out.length - 1] = cur ? cur + ' ' + word : word;
      else out.push(word);
    }
    return out;
  };
  type End = { id: string; lines: string[]; y: number; dot: number; color: string; i: number; focus: boolean };
  let ends: End[] = labelled.map((s) => {
    const i = last(s.values);
    const v = i >= 0 ? (s.values[i] as number) : 0;
    const value = fmt(v, lang, { decimals: dec });
    const lines = wrap(`${tx(s.label, lang)} ${value}`);
    return { id: s.id, lines: lines.length <= 2 && lines.every((l) => textWidth(l, 12) <= cap) ? lines : [value], y: Y(v), dot: Y(v),
      color: s.color === 'focus' ? 'var(--ink)' : 'var(--ink-secondary)', i, focus: s.color === 'focus' };
  }).filter((e) => e.i >= 0);
  const placed: End[] = [];
  const free = (y: number, e?: End) => y >= 8 && placed.every((p) => Math.abs(p.y - y) >= 15 * Math.max(p.lines.length, e?.lines.length ?? 1));
  for (const e of [...ends].sort((a, b) => Number(b.focus) - Number(a.focus))) {
    if (free(e.y, e)) { placed.push(e); continue; }
    const near = placed.reduce((a, p) => (Math.abs(p.y - e.y) < Math.abs(a.y - e.y) ? p : a));
    const y = e.y <= near.y ? near.y - 15 : near.y + 15;
    if (Math.abs(y - e.y) <= 10 && free(y, e)) placed.push({ ...e, y });
  }
  ends = narrow ? [] : placed;
  // the right margin fits the longest end label, up to 30% of the chart (at least 150px), so a label is never cut off
  if (ends.length) m.r = Math.min(cap + 16, Math.max(...ends.flatMap((e) => e.lines.map((l) => textWidth(l, 12)))) + 16);
  const pw = Math.max(60, w - m.l - m.r);
  const X = (i: number) => m.l + (n <= 1 ? pw / 2 : (i * pw) / (n - 1));

  const path = (v: Array<number | null>) => {
    let d = '', pen = false;
    v.forEach((y, i) => { if (y == null) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(y).toFixed(1) + ' '; pen = true; });
    return d;
  };

  // x ticks: the chart file's dates, else evenly spaced years; thinned to fit
  const xFmt = (s: string) => fmtPeriod(s, lang, xAxis?.format === 'month' ? 'month' : 'year');
  let xTicks = (xAxis?.ticks?.map(String) ?? []).filter((t) => xs.includes(t) || (t >= xs[0] && t <= xs[n - 1]));
  if (!xTicks.length) {
    const years = [...new Set(xs.map((s) => s.slice(0, 4)))];
    const step = Math.max(1, Math.ceil(years.length / 6));
    xTicks = years.filter((_, i) => i % step === 0).map((y) => xs.find((s) => s.startsWith(y)) as string);
  }
  const maxTicks = Math.max(2, Math.floor(pw / 56));
  if (xTicks.length > maxTicks) { const k = Math.ceil(xTicks.length / maxTicks); xTicks = xTicks.filter((_, i) => i % k === 0); }

  function locate(e: PointerEvent<SVGSVGElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) * (w / r.width);
    setHover(Math.max(0, Math.min(n - 1, Math.round(((px - m.l) / pw) * (n - 1)))));
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === 'ArrowRight') { e.preventDefault(); setHover(hover == null ? n - 1 : Math.min(n - 1, hover + 1)); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); setHover(hover == null ? n - 1 : Math.max(0, hover - 1)); }
    if (e.key === 'Home') { e.preventDefault(); setHover(0); }
    if (e.key === 'End') { e.preventDefault(); setHover(n - 1); }
    if (e.key === 'Escape') setHover(null);
  }

  let tip: ReactNode = null;
  if (hover != null) {
    const flip = X(hover) > w * 0.6;
    const rows = [...series].reverse().map((s) => ({ label: tx(s.label, lang), value: fmt(s.values[hover], lang, { decimals: dec, suffix: yAxis?.unit ? ' ' + yAxis.unit : '' }), color: s.color }));
    tip = <ChartTooltip title={fmtPeriod(xs[hover], lang, 'auto')} rows={rows}
      style={flip ? { right: w - X(hover) + 12 + 'px', top: m.t + 'px' } : { left: X(hover) + 12 + 'px', top: m.t + 'px' }} />;
  }

  const legend = allSeries.length > 1 ? (
    <Legend label={tx(spec.title, lang)} hidden={hidden}
      onToggle={(id) => setHidden((h) => (h.includes(id) ? h.filter((x) => x !== id) : [...h, id]))}
      items={[...allSeries].sort((a, b) => Number(b.color === 'focus') - Number(a.color === 'focus')).map((s) => ({ id: s.id, label: tx(s.label, lang), color: s.color, dashed: s.dashed }))} />
  ) : null;

  return (
    <div className="ac-chart ac-line">
      {legend ? <div className="ac-chart__legend">{legend}</div> : null}
      <div ref={ref} className="gl-chart" data-ready={ready ? '1' : undefined} style={{ height: height + 'px' }}>
        <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`} role="img" aria-label={tx(spec.alt, lang)} tabIndex={0}
          onKeyDown={onKey} onBlur={() => setHover(null)} onPointerMove={locate} onPointerLeave={() => setHover(null)}>
          {yLabel ? <text x={0} y={13} className="ac-axis-label">{yLabel}</text> : null}
          {(spec.bands ?? []).map((b, i) => {
            const x0 = X(idx(b.from)), x1 = X(idx(b.to));
            return <rect key={'b' + i} x={x0} y={m.t} width={Math.max(1, x1 - x0)} height={ph} className="gl-chart__band" />;
          })}
          {ticks.map((t) => (
            <g key={'y' + t}>
              <line x1={m.l} x2={m.l + pw} y1={Y(t)} y2={Y(t)} className={t === 0 ? 'gl-chart__zero' : 'gl-chart__grid'} />
              <text x={m.l - 8} y={Y(t) + 4} textAnchor="end" className="gl-chart__tick">{fmt(t, lang, { decimals: dec })}</text>
            </g>
          ))}
          {xTicks.map((t, i) => {
            const x = X(idx(t));
            return <text key={'x' + i} x={x} y={m.t + ph + 18} textAnchor={x - m.l < 16 ? 'start' : m.l + pw - x < 16 ? 'end' : 'middle'} className="gl-chart__tick">{xFmt(t)}</text>;
          })}
          {xLabel ? <text x={m.l + pw / 2} y={height - 4} textAnchor="middle" className="ac-axis-label ac-axis-label--x">{xLabel}</text> : null}
          {(spec.referenceLines ?? []).filter((r) => r.axis === 'y' && r.value >= lo && r.value <= hi).map((r, i) => (
            <g key={'r' + i}>
              <line x1={m.l} x2={m.l + pw} y1={Y(r.value)} y2={Y(r.value)} className="ac-ref" />
            </g>
          ))}
          {annotations.map((a, i) => {
            const x = X(idx(a.x));
            const label = tx(a.label, lang);
            const lw = textWidth(label, 12);
            // right of the line if it fits, else left of it, else clamped inside the plot
            const lx = x + 5 + lw <= m.l + pw ? x + 5 : x - 5 - lw >= 0 ? x - 5 - lw : Math.max(0, m.l + pw - lw);
            return (
              <g key={'a' + i}>
                <line x1={x} x2={x} y1={m.t - 14} y2={m.t + ph} className="ac-annot" />
                <text x={lx} y={m.t - 5} className="ac-annot-label">{label}</text>
              </g>
            );
          })}
          {series.map((s) => (
            <path key={s.id} d={path(s.values)} className={'gl-chart__line' + (s.dashed ? ' is-dashed' : '') + (s.color === 'focus' ? ' ac-line--focus' : '')} style={{ stroke: colorOf(s.color) }} />
          ))}
          {series.map((s) => {
            const i = last(s.values);
            return i >= 0 ? <circle key={'d' + s.id} cx={X(i)} cy={Y(s.values[i] as number)} r={4} className="gl-chart__dot" style={{ fill: colorOf(s.color) }} /> : null;
          })}
          {(spec.referenceLines ?? []).filter((r) => r.axis === 'y' && r.label && r.value >= lo && r.value <= hi).map((r, i) => (
            <text key={'rl' + i} x={m.l + pw - 4} y={Y(r.value) - 5} textAnchor="end" className="ac-ref-label">{tx(r.label, lang)}</text>
          ))}
          {(spec.bands ?? []).map((b, i) => {
            if (!b.label || narrow) return null;
            const label = tx(b.label, lang);
            const x = Math.max(0, Math.min(X(idx(b.from)) + 4, w - textWidth(label, 12) - 2));   // inside the chart's right edge
            return <text key={'bl' + i} x={x} y={m.t + 13} className="gl-chart__bandlabel ac-bandlabel">{label}</text>;
          })}
          {ends.map((e) => (
            <g key={'l' + e.id}>
              {Math.abs(e.y - e.dot) > 3 ? <line x1={X(e.i) + 4} x2={X(e.i) + 8} y1={e.dot} y2={e.y} className="ac-annot" /> : null}
              <text x={X(e.i) + 9} y={e.y + 4 - (e.lines.length - 1) * 6.5} className={'ac-endlabel' + (e.focus ? ' is-focus' : '')}>
                {e.lines.map((l, k) => <tspan key={k} x={X(e.i) + 9} dy={k ? 13 : 0}>{l}</tspan>)}
              </text>
            </g>
          ))}
          {hover != null ? (
            <g>
              <line x1={X(hover)} x2={X(hover)} y1={m.t} y2={m.t + ph} className="gl-chart__cross" />
              {series.map((s) => { const v = s.values[hover]; return v == null ? null : <circle key={'h' + s.id} cx={X(hover)} cy={Y(v)} r={4} className="gl-chart__dot" style={{ fill: colorOf(s.color) }} />; })}
            </g>
          ) : null}
        </svg>
        {tip}
      </div>
    </div>
  );
}
