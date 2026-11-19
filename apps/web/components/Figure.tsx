import { t as gt, type Lang } from '@glacier/i18n';
import { ChartView, StatTiles, fmtPeriod, tx, type ChartSpec } from '@articles/charts';
import { s } from '@/lib/strings';
import { Cites, type MarkCtx } from './Marks';
import { sourceLine } from '@/lib/text';

const WIDE = new Set(['line', 'scatter']);

/** An article figure: number and takeaway, title and subtitle, the plot (or tiles) with its table view,
 *  how to read it, notes, the source line, the "About this chart" panel and the CSV (Glacier Figure + ChartCard). */
export function Figure({ spec, n, lang, ctx }: { spec: ChartSpec & { csvUrl?: string }; n: number; lang: Lang; ctx: MarkCtx }) {
  const m = spec.meta ?? {};
  const srcIds = m.sources ?? [];
  const last = m.lastObservation ? fmtPeriod(m.lastObservation, lang, 'auto') : null;
  const width = WIDE.has(spec.form) ? 'wide' : 'column';
  return (
    <figure id={`fig-${spec.id}`} data-chart={spec.id} className={`ac-figure ac-figure--${width}`} lang={lang}>
      <div className="ac-figure__head">
        <p className="ac-figure__num">{s(lang, 'figure', { n })}</p>
        {spec.headline ? <p className="ac-figure__headline">{tx(spec.headline, lang)}</p> : null}
        <p className="ac-figure__title">{tx(spec.title, lang)}{spec.subtitle ? <span className="ac-figure__sub">{tx(spec.subtitle, lang)}</span> : null}</p>
      </div>
      <div className="ac-figure__body">
        {spec.form === 'stat-tiles'
          ? <div role="img" aria-label={tx(spec.alt, lang)}><StatTiles tiles={spec.tiles ?? []} lang={lang} renderCite={(ids) => <Cites ids={ids} ctx={ctx} />} /></div>
          : <ChartView spec={spec} lang={lang} />}
      </div>
      <figcaption className="ac-figure__foot">
        {spec.howToRead ? <p className="ac-figure__how"><span>{s(lang, 'howToRead')}.</span> {tx(spec.howToRead, lang)}</p> : null}
        {(spec.notes ?? []).map((x, i) => <p key={i} className="ac-figure__note">{tx(x, lang)}</p>)}
        <p className="ac-figure__source">
          {sourceLine(tx(m.attribution, lang), lang)}
          {last ? <span className="ac-figure__asof">{' · '}{s(lang, 'dataTo', { date: last })}</span> : null}
          {srcIds.length ? <Cites ids={srcIds} ctx={ctx} /> : null}
        </p>
        <div className="ac-figure__tools">
          <details className="ac-about">
            <summary>{s(lang, 'aboutChart')}</summary>
            <dl>
              {m.definition ? <><dt>{s(lang, 'definition')}</dt><dd>{tx(m.definition, lang)}</dd></> : null}
              {m.calculation ? <><dt>{s(lang, 'calculation')}</dt><dd>{tx(m.calculation, lang)}</dd></> : null}
              {m.provider ? <><dt>{s(lang, 'provider')}</dt><dd>{m.provider}</dd></> : null}
              {m.keys?.length ? <><dt>{s(lang, 'seriesKey')}</dt><dd className="ac-mono">{m.keys.join(', ')}</dd></> : null}
              {m.span ? <><dt>{s(lang, 'span')}</dt><dd>{fmtPeriod(m.span[0], lang, 'auto')} – {fmtPeriod(m.span[1], lang, 'auto')}</dd></> : null}
              {m.lastObservation ? <><dt>{s(lang, 'lastObservation')}</dt><dd>{last}</dd></> : null}
              {m.retrieved ? <><dt>{s(lang, 'retrieved')}</dt><dd>{fmtPeriod(m.retrieved, lang, 'auto')}</dd></> : null}
              {m.licence ? <><dt>{s(lang, 'licence')}</dt><dd>{m.licence}</dd></> : null}
              {srcIds.length ? <><dt>{s(lang, 'sources')}</dt><dd>{srcIds.map((id, i) => <span key={id}>{i ? ', ' : ''}<a href={`#ref-${id}`}>{ctx.sources.get(id)?.title ?? id}</a></span>)}</dd></> : null}
            </dl>
          </details>
          {spec.csvUrl ? (
            <a className="gl-btn gl-btn--quiet gl-btn--sm ac-csv" href={spec.csvUrl} download>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 4v11" /><path d="M7.5 10.5 12 15l4.5-4.5" /><path d="M5 19.5h14" /></svg>
              {gt(lang, 'download')}
            </a>
          ) : null}
        </div>
      </figcaption>
    </figure>
  );
}
