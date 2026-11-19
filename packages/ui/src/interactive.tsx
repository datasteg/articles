'use client';
import { useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode, type FormEvent } from 'react';
import { formatNumber, t, type Lang } from '@glacier/i18n';
import { Button } from './actions';
import { ChartTooltip } from './data';
import { EmptyState, Notice, Skeleton } from './feed';
import { cx, seriesColor, Icon, StrataArt, type SeriesColor } from './util';

function useControlled<T>(value: T | undefined, defaultValue: T, onChange?: (v: T) => void): [T, (v: T) => void] {
  const [inner, setInner] = useState<T>(defaultValue);
  const controlled = value !== undefined;
  return [controlled ? (value as T) : inner, (v: T) => { if (!controlled) setInner(v); onChange?.(v); }];
}

/* ---------------- SubscribeBox ---------------- */
export function SubscribeBox(p: {
  lang: Lang; title?: string; body?: string; placeholder?: string; buttonLabel?: string; fine?: string; doneMessage?: string;
  /** Called with the address; the box shows its confirmation once this resolves. */
  onSubmit?: (email: string) => void | Promise<void>;
  /** POST {email, lang} as JSON to this URL instead of onSubmit. */
  action?: string;
  className?: string;
}) {
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = (e.currentTarget.elements.namedItem('email') as HTMLInputElement).value;
    setError(null);
    try {
      if (p.onSubmit) await p.onSubmit(email);
      else if (p.action) {
        const r = await fetch(p.action, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email, lang: p.lang }) });
        if (!r.ok) throw new Error(String(r.status));
      }
      setDone(true);
    } catch {
      setError(p.lang === 'ko' ? '지금은 구독할 수 없습니다. 잠시 후 다시 시도해 주세요.' : 'Subscribing failed. Try again in a moment.');
    }
  }
  return (
    <section className={cx('gl-sub', p.className)} aria-labelledby={id + '-t'}>
      <StrataArt />
      <div className="gl-sub__inner">
        <h2 className="gl-sub__title" id={id + '-t'}>{p.title ?? t(p.lang, 'sub.title')}</h2>
        {p.body ? <p className="gl-sub__body">{p.body}</p> : null}
        {done ? (
          <p className="gl-sub__done" role="status">{p.doneMessage ?? t(p.lang, 'sub.done')}</p>
        ) : (
          <form className="gl-sub__form" onSubmit={submit}>
            <label className="gl-visually-hidden" htmlFor={id + '-e'}>{t(p.lang, 'email')}</label>
            <input className="gl-sub__input" id={id + '-e'} name="email" type="email" required autoComplete="email" placeholder={p.placeholder ?? 'you@institution.org'} />
            <Button variant="deep" type="submit">{p.buttonLabel ?? t(p.lang, 'subscribe')}</Button>
          </form>
        )}
        {error ? <p className="gl-sub__fine" role="alert">{error}</p> : null}
        {p.fine && !done ? <p className="gl-sub__fine">{p.fine}</p> : null}
      </div>
    </section>
  );
}

/* ---------------- SegmentedControl ---------------- */
export interface SelectOption { value: string; label: string }
export function SegmentedControl(p: { options: SelectOption[]; value?: string; defaultValue?: string; onChange?: (v: string) => void; label: string; size?: 'md' | 'sm'; className?: string }) {
  const [val, setVal] = useControlled(p.value, p.defaultValue ?? p.options[0]?.value ?? '', p.onChange);
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  function onKey(e: KeyboardEvent, i: number) {
    const n = p.options.length;
    let j: number | null = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') j = (i + 1) % n;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') j = (i - 1 + n) % n;
    if (j !== null) { e.preventDefault(); setVal(p.options[j].value); refs.current[j]?.focus(); }
  }
  return (
    <div className={cx('gl-seg', p.size === 'sm' && 'gl-seg--sm', p.className)} role="radiogroup" aria-label={p.label}>
      {p.options.map((o, i) => {
        const sel = o.value === val;
        return (
          <button key={o.value} ref={(el) => { refs.current[i] = el; }} type="button" role="radio" aria-checked={sel} tabIndex={sel ? 0 : -1} className="gl-seg__opt" onClick={() => setVal(o.value)} onKeyDown={(e) => onKey(e, i)}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/* ---------------- Switch ---------------- */
export function Switch(p: { label: ReactNode; checked?: boolean; defaultChecked?: boolean; onChange?: (on: boolean) => void; disabled?: boolean; className?: string }) {
  const [on, setOn] = useControlled(p.checked, !!p.defaultChecked, p.onChange);
  const id = useId();
  return (
    <div className={cx('gl-switch', p.className)}>
      <button type="button" role="switch" id={id} aria-checked={on} className="gl-switch__track" onClick={() => setOn(!on)} disabled={p.disabled}>
        <span className="gl-switch__thumb" />
      </button>
      <label htmlFor={id} className="gl-switch__label">{p.label}</label>
    </div>
  );
}

/* ---------------- Legend ---------------- */
export interface LegendItem { id?: string; label: string; color?: SeriesColor; type?: 'line' | 'bar' | 'dot'; dashed?: boolean }
export function Legend(p: { items: LegendItem[]; hidden?: string[]; onToggle?: (id: string) => void; label?: string; className?: string }) {
  const hidden = p.hidden ?? [];
  return (
    <ul className={cx('gl-legend', p.className)} aria-label={p.label}>
      {p.items.map((it) => {
        const key = <span className={cx('gl-legend__key', 'gl-legend__key--' + (it.type ?? 'line'), it.dashed && 'is-dashed')} style={{ '--k': seriesColor(it.color) } as CSSProperties} aria-hidden />;
        const off = it.id ? hidden.includes(it.id) : false;
        return (
          <li key={it.id ?? it.label}>
            {p.onToggle && it.id
              ? <button type="button" className={cx('gl-legend__item', off && 'is-off')} aria-pressed={!off} onClick={() => p.onToggle!(it.id!)}>{key}{it.label}</button>
              : <span className="gl-legend__item">{key}{it.label}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/* ---------------- charts ---------------- */
function useWidth(ref: React.RefObject<HTMLDivElement | null>, fallback: number): number {
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const measure = () => { const cw = Math.round(el.getBoundingClientRect().width); if (cw > 0) setW(cw); };
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}
function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) { min -= 1; max += 1; }
  const raw = (max - min) / count, mag = Math.pow(10, Math.floor(Math.log10(raw))), err = raw / mag;
  const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
  const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, out: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) out.push(+v.toFixed(10));
  return out;
}

export interface LineSeries { id: string; label: string; values: Array<number | null>; color?: SeriesColor; dashed?: boolean }
export interface ChartBand { from: number; to: number; label?: string }
export function LineChart(p: {
  lang: Lang; x: string[]; series: LineSeries[]; hidden?: string[]; height?: number;
  yFormat?: (v: number) => string; yTickFormat?: (v: number) => string; yMin?: number; yMax?: number; yTickCount?: number;
  bands?: ChartBand[]; area?: boolean; endLabels?: boolean; labelSpace?: number; scale?: number;
  /** The takeaway, for screen readers. */
  ariaLabel: string; width?: number; className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const w = useWidth(ref, p.width ?? 640);
  const sc = p.scale ?? 1;
  const height = p.height ?? 320;
  const hidden = p.hidden ?? [];
  const series = p.series.filter((s) => !hidden.includes(s.id));
  const xs = p.x;
  const n = xs.length;
  const fmt = p.yFormat ?? ((v: number) => formatNumber(v, { lang: p.lang, decimals: 1 }));
  const all: number[] = [];
  series.forEach((s) => s.values.forEach((v) => { if (v != null) all.push(v); }));
  if (p.yMin != null) all.push(p.yMin);
  if (p.yMax != null) all.push(p.yMax);
  const ticks = niceTicks(Math.min(...(all.length ? all : [0])), Math.max(...(all.length ? all : [1])), p.yTickCount ?? 4);
  const y0 = ticks[0], y1 = ticks[ticks.length - 1];
  const tickFmt = p.yTickFormat ?? fmt;
  const m = { t: 12 * sc, r: 12 * sc, b: 28 * sc, l: 44 * sc };
  const ph = height - m.t - m.b;
  const Y = (v: number) => m.t + ph - ((v - y0) / (y1 - y0)) * ph;
  const last = (vals: Array<number | null>) => { for (let i = vals.length - 1; i >= 0; i--) if (vals[i] != null) return i; return -1; };
  const ends = series.map((s) => { const i = last(s.values); return { s, i, y: i >= 0 ? Y(s.values[i] as number) : 0 }; });
  const sorted = [...ends].sort((a, b) => a.y - b.y);
  let collide = false;
  for (let k = 1; k < sorted.length; k++) if (sorted[k].y - sorted[k - 1].y < 15 * sc) collide = true;
  /* direct end-labels only when they separate cleanly; otherwise the Legend carries identity */
  const showLabels = p.endLabels !== false && series.length <= 4 && !collide && w >= 480;
  if (showLabels) m.r = (p.labelSpace ?? 96) * sc;
  const pw = Math.max(40, w - m.l - m.r);
  const X = (i: number) => m.l + (n <= 1 ? pw / 2 : (i * pw) / (n - 1));
  const path = (vals: Array<number | null>) => {
    let d = '', pen = false;
    vals.forEach((v, i) => { if (v == null) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1) + ' '; pen = true; });
    return d;
  };
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(pw / (64 * sc)))));
  const [hover, setHover] = useState<number | null>(null);
  function locate(e: PointerEvent<SVGSVGElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) * (w / r.width);
    const i = Math.round((px - m.l) / (pw / Math.max(1, n - 1)));
    setHover(Math.max(0, Math.min(n - 1, i)));
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === 'ArrowRight') { e.preventDefault(); setHover(hover == null ? 0 : Math.min(n - 1, hover + 1)); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); setHover(hover == null ? n - 1 : Math.max(0, hover - 1)); }
    if (e.key === 'Escape') setHover(null);
  }
  let tip: ReactNode = null;
  if (hover != null) {
    const flip = X(hover) > w * 0.62;
    tip = (
      <ChartTooltip
        title={xs[hover]}
        style={flip ? { right: w - X(hover) + 12 * sc + 'px', top: m.t + 'px' } : { left: X(hover) + 12 * sc + 'px', top: m.t + 'px' }}
        rows={series.map((s) => ({ label: s.label, value: s.values[hover] == null ? '–' : fmt(s.values[hover] as number), color: s.color }))}
      />
    );
  }
  return (
    <div ref={ref} className={cx('gl-chart', p.className)} style={{ '--sc': sc, height: height + 'px' } as CSSProperties}>
      <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`} role="img" aria-label={p.ariaLabel} tabIndex={0} onKeyDown={onKey} onBlur={() => setHover(null)} onPointerMove={locate} onPointerLeave={() => setHover(null)}>
        {(p.bands ?? []).map((b, i) => (
          <g key={'b' + i}>
            <rect x={X(b.from)} y={m.t} width={Math.max(1, X(b.to) - X(b.from))} height={ph} className="gl-chart__band" />
            {b.label ? <text x={X(b.from) + 4 * sc} y={m.t + 12 * sc} className="gl-chart__bandlabel">{b.label}</text> : null}
          </g>
        ))}
        {ticks.map((tv) => (
          <g key={'y' + tv}>
            <line x1={m.l} x2={m.l + pw} y1={Y(tv)} y2={Y(tv)} className={tv === 0 ? 'gl-chart__zero' : 'gl-chart__grid'} />
            <text x={m.l - 8 * sc} y={Y(tv) + 4 * sc} textAnchor="end" className="gl-chart__tick">{tickFmt(tv)}</text>
          </g>
        ))}
        {xs.map((lab, i) =>
          (i % every === 0 || i === n - 1) && !(i !== n - 1 && n - 1 - i < every * 0.6)
            ? <text key={'x' + i} x={X(i)} y={height - 8 * sc} textAnchor={i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'} className="gl-chart__tick">{lab}</text>
            : null,
        )}
        {series.map((s) => (
          <g key={s.id}>
            {p.area && series.length === 1
              ? <path d={path(s.values) + 'L' + X(last(s.values)) + ' ' + Y(Math.max(y0, 0)) + ' L' + X(0) + ' ' + Y(Math.max(y0, 0)) + ' Z'} className="gl-chart__area" style={{ fill: seriesColor(s.color) }} />
              : null}
            <path d={path(s.values)} className={cx('gl-chart__line', s.dashed && 'is-dashed')} style={{ stroke: seriesColor(s.color) }} />
          </g>
        ))}
        {ends.map((e) => (e.i >= 0 ? <circle key={'e' + e.s.id} cx={X(e.i)} cy={e.y} r={4 * sc} className="gl-chart__dot" style={{ fill: seriesColor(e.s.color) }} /> : null))}
        {showLabels ? ends.map((e) => (e.i >= 0 ? <text key={'l' + e.s.id} x={X(e.i) + 10 * sc} y={e.y + 4 * sc} className="gl-chart__endlabel">{e.s.label}</text> : null)) : null}
        {hover != null ? (
          <g>
            <line x1={X(hover)} x2={X(hover)} y1={m.t} y2={m.t + ph} className="gl-chart__cross" />
            {series.map((s) => { const v = s.values[hover]; return v == null ? null : <circle key={'h' + s.id} cx={X(hover)} cy={Y(v)} r={4 * sc} className="gl-chart__dot" style={{ fill: seriesColor(s.color) }} />; })}
          </g>
        ) : null}
      </svg>
      {tip}
    </div>
  );
}

function barPath(x0: number, x1: number, y: number, hgt: number, r: number): string {
  const len = Math.abs(x1 - x0);
  r = Math.min(r, len / 2, hgt / 2);
  if (len < 0.5) return '';
  if (x1 >= x0) return `M${x0} ${y}H${x1 - r}A${r} ${r} 0 0 1 ${x1} ${y + r}V${y + hgt - r}A${r} ${r} 0 0 1 ${x1 - r} ${y + hgt}H${x0}Z`;
  return `M${x0} ${y}H${x1 + r}A${r} ${r} 0 0 0 ${x1} ${y + r}V${y + hgt - r}A${r} ${r} 0 0 0 ${x1 + r} ${y + hgt}H${x0}Z`;
}

export interface BarDatum { label: string; value: number; color?: SeriesColor }
export function BarChart(p: {
  lang: Lang; data: BarDatum[]; format?: (v: number) => string; color?: SeriesColor; highlight?: string; diverging?: boolean;
  labelWidth?: number; barThickness?: number; scale?: number; ariaLabel: string; width?: number; className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const w = useWidth(ref, p.width ?? 640);
  const sc = p.scale ?? 1;
  const fmt = p.format ?? ((v: number) => formatNumber(v, { lang: p.lang, decimals: 1 }));
  const thick = Math.min(24 * sc, p.barThickness ?? 20 * sc), gap = 12 * sc;
  const labelW = (p.labelWidth ?? 120) * sc, valueW = 56 * sc;
  const vals = p.data.map((d) => d.value);
  const hasNeg = vals.some((v) => v < 0);
  const min = Math.min(0, ...vals), max = Math.max(0, ...vals);
  const left = labelW + (hasNeg ? valueW : 0), right = w - valueW;
  const X = (v: number) => left + ((v - min) / (max - min || 1)) * (right - left);
  const height = p.data.length * (thick + gap) + gap;
  const [hover, setHover] = useState<number | null>(null);
  const colorOf = (d: BarDatum) => {
    if (d.color) return seriesColor(d.color);
    if (p.highlight != null) return d.label === p.highlight ? 'var(--viz-focus)' : 'var(--viz-context)';
    if (p.diverging) return d.value < 0 ? 'var(--div-neg-2)' : 'var(--div-pos-2)';
    return seriesColor(p.color ?? 1);
  };
  return (
    <div ref={ref} className={cx('gl-chart', 'gl-barchart', p.className)} style={{ '--sc': sc } as CSSProperties}>
      <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`} role="img" aria-label={p.ariaLabel}>
        {p.data.map((d, i) => {
          const y = gap + i * (thick + gap);
          const x0 = X(0), x1 = X(d.value);
          return (
            <g key={d.label} className={cx('gl-bar', hover === i && 'is-hover')} tabIndex={0} aria-label={d.label + ': ' + fmt(d.value)} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}>
              <rect x={0} y={y - gap / 2} width={w} height={thick + gap} fill="transparent" />
              <text x={labelW - 12 * sc} y={y + thick / 2 + 4 * sc} textAnchor="end" className="gl-chart__cat">{d.label}</text>
              <path d={barPath(x0, x1, y, thick, 4 * sc)} style={{ fill: colorOf(d) }} />
              <text x={d.value < 0 ? x1 - 6 * sc : x1 + 6 * sc} y={y + thick / 2 + 4 * sc} textAnchor={d.value < 0 ? 'end' : 'start'} className="gl-chart__value">{fmt(d.value)}</text>
            </g>
          );
        })}
        <line x1={X(0)} x2={X(0)} y1={gap / 2} y2={height - gap / 2} className="gl-chart__zero" />
      </svg>
    </div>
  );
}

/* ---------------- ChartCard ---------------- */
export function ChartCard(p: {
  lang: Lang; title: string; subtitle?: string; controls?: ReactNode; legend?: ReactNode; table?: ReactNode; children?: ReactNode;
  source?: string; updated?: string; footnote?: ReactNode; onDownload?: () => void; downloadHref?: string; downloadName?: string;
  state?: 'ready' | 'loading' | 'refetching' | 'empty' | 'error';
  height?: number; emptyTitle?: string; emptyBody?: string; errorTitle?: string; errorMessage?: ReactNode; className?: string;
}) {
  const [view, setView] = useState('chart');
  const id = useId();
  const state = p.state ?? 'ready';
  let body: ReactNode;
  if (state === 'loading') body = <Skeleton lang={p.lang} variant="chart" height={p.height} />;
  else if (state === 'empty') body = <EmptyState lang={p.lang} title={p.emptyTitle ?? t(p.lang, 'empty')} body={p.emptyBody} />;
  else if (state === 'error') body = <Notice lang={p.lang} tone="critical" title={p.errorTitle}>{p.errorMessage}</Notice>;
  else body = view === 'table' && p.table ? p.table : p.children;
  const hasDownload = p.onDownload || p.downloadHref;
  return (
    <section className={cx('gl-card', p.className)} aria-labelledby={id} lang={p.lang}>
      <div className="gl-card__head">
        <div>
          <h3 className="gl-card__title" id={id}>{p.title}</h3>
          {p.subtitle ? <p className="gl-card__sub">{p.subtitle}</p> : null}
        </div>
        <div className="gl-card__tools">
          {p.controls ?? null}
          {p.table ? <SegmentedControl size="sm" label={p.title} value={view} onChange={setView} options={[{ value: 'chart', label: t(p.lang, 'chart') }, { value: 'table', label: t(p.lang, 'table') }]} /> : null}
        </div>
      </div>
      {p.legend && view === 'chart' && state === 'ready' ? <div className="gl-card__legend">{p.legend}</div> : null}
      <div className={cx('gl-card__body', state === 'refetching' && 'is-refetching')} aria-busy={state === 'refetching' || state === 'loading' ? true : undefined}>{body}</div>
      {p.source || p.updated || hasDownload || p.footnote ? (
        <div className="gl-card__foot">
          <p className="gl-card__source">
            {p.source ? t(p.lang, 'source') + p.source : null}
            {p.source && p.updated ? <span className="gl-sep" aria-hidden>·</span> : null}
            {p.updated ? t(p.lang, 'updated') + ' ' + p.updated : null}
            {p.footnote ? <span className="gl-card__note">{p.footnote}</span> : null}
          </p>
          {p.downloadHref
            ? <a className="gl-btn gl-btn--quiet gl-btn--sm" href={p.downloadHref} download={p.downloadName}><Icon name="download" />{t(p.lang, 'download')}</a>
            : p.onDownload ? <Button variant="quiet" size="sm" icon="download" onClick={p.onDownload}>{t(p.lang, 'download')}</Button> : null}
        </div>
      ) : null}
    </section>
  );
}

/* ---------------- DataTable ---------------- */
export interface DataColumn<R> {
  key: string; label: ReactNode; align?: 'left' | 'right'; sortable?: boolean;
  /** Decimals for numeric cells (default 2). */
  decimals?: number; render?: (value: unknown, row: R) => ReactNode; width?: number | string;
}
type Sort = { key: string; dir: 'asc' | 'desc' };
export function DataTable<R extends Record<string, unknown>>(p: {
  lang: Lang; columns: DataColumn<R>[]; rows: R[]; caption: string; showCaption?: boolean; defaultSort?: Sort; dense?: boolean; className?: string;
}) {
  const [sort, setSort] = useState<Sort | null>(p.defaultSort ?? null);
  const locale = p.lang === 'ko' ? 'ko-KR' : 'en-GB';
  const rows = [...p.rows];
  if (sort) {
    rows.sort((a, b) => {
      const x = a[sort.key], y = b[sort.key];
      const r = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), locale);
      return sort.dir === 'desc' ? -r : r;
    });
  }
  const toggle = (c: DataColumn<R>) =>
    setSort(sort && sort.key === c.key ? { key: c.key, dir: sort.dir === 'asc' ? 'desc' : 'asc' } : { key: c.key, dir: c.align === 'right' ? 'desc' : 'asc' });
  return (
    <div className={cx('gl-table-wrap', p.className)} lang={p.lang} tabIndex={0} role="region" aria-label={p.caption}>
      <table className={cx('gl-table', p.dense && 'gl-table--dense')}>
        {p.caption ? <caption className={p.showCaption ? 'gl-table__caption' : 'gl-visually-hidden'}>{p.caption}</caption> : null}
        <thead>
          <tr>
            {p.columns.map((c) => {
              const active = sort && sort.key === c.key;
              return (
                <th key={c.key} scope="col" className={c.align === 'right' ? 'is-num' : undefined} style={c.width ? { width: c.width } : undefined}
                  aria-sort={active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : c.sortable ? 'none' : undefined}>
                  {c.sortable ? <button type="button" className={cx('gl-table__sort', !!active && 'is-active')} onClick={() => toggle(c)}>{c.label}<Icon name="sort" /></button> : c.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={String(r.id ?? i)}>
              {p.columns.map((c, j) => {
                const v = r[c.key];
                const content = c.render ? c.render(v, r) : typeof v === 'number' ? formatNumber(v, { lang: p.lang, decimals: c.decimals ?? 2 }) : (v as ReactNode);
                const cls = c.align === 'right' ? 'is-num' : undefined;
                return j === 0 ? <th key={c.key} scope="row" className={cls}>{content}</th> : <td key={c.key} className={cls}>{content}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
