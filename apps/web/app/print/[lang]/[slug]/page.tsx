import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { LANGS, t as gt, type Lang } from '@glacier/i18n';
import { BarChart, DumbbellChart, LineChart, ScatterChart, StatTiles, fmt, fmtPeriod, tx, type ChartSpec } from '@articles/charts';
import { Cites, Marks, type MarkCtx } from '@/components/Marks';
import { ARTICLES, GLOSSARY, getArticle, getPipeline, type Article, type Block, type Source } from '@/lib/content';
import { citationBibtex, citationText } from '@/lib/citation';
import { citations, figureNumbers } from '@/lib/cites';
import { s } from '@/lib/strings';
import { sourceLine } from '@/lib/text';

// The PDF edition (contracts/content.md § PDF): the article set as a journal page for A4 paper. One calm column of
// serif text, figures across the column, numbered sections and references, and the article's citation and the
// disclaimer at the end. Chromium prints it (pipeline/artools/pdf.py); app/print.css holds the layout.

type Params = Promise<{ lang: string; slug: string }>;
export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.flatMap((lang) => ARTICLES.filter((a) => a.editions[lang]).map((a) => ({ lang, slug: a.slug })));
}

const plain = (x: string) => x.replace(/\s*\[\[[^\]]*\]\]/g, '').replace(/\(\(([^)|]+)(?:\|([^)]*))?\)\)/g, (_m: string, id: string, text: string) => text || id).replace(/\*([^*]+)\*/g, '$1');
/** A string for CSS `content`: quoted, escaped, on one line, with no way out of the <style> element. */
const cssString = (x: string) => `"${x.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/</g, '\\3C ').replace(/[\r\n]+/g, ' ')}"`;
const short = (x: string, n: number) => (x.length <= n ? x : `${x.slice(0, n - 1).replace(/[\s,;:–—-]+\S*$/, '')}…`);

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { lang, slug } = await params;
  const ed = getArticle(slug)?.editions[lang as Lang];
  return ed ? { title: plain(ed.title), description: plain(ed.dek) } : {};
}

const GROUPS: Array<{ key: 'ref.research' | 'ref.speeches' | 'ref.data' | 'ref.other'; kinds: Source['kind'][] }> = [
  { key: 'ref.research', kinds: ['paper', 'policy-note', 'report'] },
  { key: 'ref.speeches', kinds: ['speech', 'web'] },
  { key: 'ref.data', kinds: ['dataset'] },
];

export default async function PrintPage({ params }: { params: Params }) {
  const { lang: raw, slug } = await params;
  const lang = raw as Lang;
  const a = getArticle(slug);
  const ed = a?.editions[lang];
  if (!a || !ed) notFound();
  const meta = a.meta;
  const type = getPipeline(meta.type);
  const { nums } = citations(a, ed, { keyNumbers: s(lang, 'keyNumbers'), findings: s(lang, 'findingsTitle'), insight: ed.insight?.label ?? gt(lang, 'ourRead') });
  const figs = figureNumbers(ed);
  const ctx: MarkCtx = { lang, nums, sources: new Map(a.sources.map((x) => [x.id, x])), glossary: GLOSSARY, termContext: new Map(a.terms.map((x) => [x.id, x.context])), print: true };
  const other: Lang = lang === 'en' ? 'ko' : 'en';
  const url = meta.citation ? tx(meta.citation.url, lang) : `https://articles.datasteg.com/${lang}/a/${slug}`;
  const otherUrl = a.editions[other] ? (meta.citation ? tx(meta.citation.url, other) : url.replace(`/${lang}/a/`, `/${other}/a/`)) : null;
  const bare = (u: string) => u.replace(/^https?:\/\//, '');
  const title = plain(ed.title);
  const published = fmtPeriod(meta.date, lang, 'auto');
  const terms = a.terms.filter((x) => GLOSSARY[x.id]);
  // the day it is printed, in the newsroom's calendar (Seoul), as articles are dated
  const made = fmtPeriod(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date()), lang, 'auto');
  // running heads and feet (CSS page-margin boxes): the publication on the left, the title on the right, the
  // article's address and the page number underneath; none on the first page, which has the masthead
  const pageCss = `@page { @top-right { content: ${cssString(short(title, lang === 'ko' ? 34 : 64))}; } @bottom-left { content: ${cssString(bare(url))}; } }
@page :first { @top-right { content: none; } }`;

  return (
    <article className="pf" lang={lang}>
      <style>{pageCss}</style>
      <header className="pf-mast">
        <p className="pf-mast__name"><span className="pf-mast__word">datasteg</span> <span className="pf-mast__pub">articles</span></p>
        <p className="pf-mast__meta">{type ? tx(type.name, lang) : null}{type ? ' · ' : null}{published}</p>
      </header>
      <div className="pf-strata" aria-hidden><span /><span /><span /></div>

      <header className="pf-head">
        <p className="pf-kicker">{ed.kicker}</p>
        <h1 className="pf-title">{title}</h1>
        <p className="pf-dek">{plain(ed.dek)}</p>
        <p className="pf-byline">
          <span className="pf-byline__name">{ed.byline ?? 'datasteg'}</span>
          <span>{published}</span>
          {meta.readTime?.[lang] ? <span>{gt(lang, 'readTime', { n: meta.readTime[lang] as number })}</span> : null}
        </p>
      </header>

      {ed.keyNumbers?.length ? (
        <section className="pf-keynums" aria-label={s(lang, 'keyNumbers')}>
          <h2 className="pf-label">{s(lang, 'keyNumbers')}</h2>
          <StatTiles lang={lang} tiles={ed.keyNumbers.map((k) => ({ value: k.value, label: k.label, cite: k.cite }))} renderCite={(ids) => <Cites ids={ids} ctx={ctx} />} />
        </section>
      ) : null}

      <div className="pf-front">
        <aside className="pf-info" aria-label={s(lang, 'print.info')}>
          <h2 className="pf-label">{s(lang, 'print.info')}</h2>
          <dl>
            {type ? <><dt>{s(lang, 'print.type')}</dt><dd>{tx(type.name, lang)}</dd></> : null}
            <dt>{s(lang, 'print.published')}</dt><dd>{published}</dd>
            {meta.updated ? <><dt>{s(lang, 'print.updated')}</dt><dd>{fmtPeriod(meta.updated, lang, 'auto')}</dd></> : null}
            {meta.topics.length ? <><dt>{s(lang, 'print.topics')}</dt><dd>{meta.topics.map((x) => tx(x.label, lang)).join(', ')}</dd></> : null}
            <dt>{s(lang, 'print.online')}</dt><dd><a href={url}>{bare(url)}</a></dd>
            {otherUrl ? <><dt>{s(lang, 'print.other')}</dt><dd><a href={otherUrl}>{bare(otherUrl)}</a></dd></> : null}
            <dt>{s(lang, 'print.data')}</dt><dd>{s(lang, 'print.dataText')}</dd>
          </dl>
        </aside>
        <section id="findings" className="pf-findings" aria-labelledby="findings-h">
          <h2 id="findings-h" className="pf-label">{s(lang, 'findingsTitle')}</h2>
          <ol>
            {ed.findings.map((f, i) => (
              <li key={i}><span className="pf-findings__num" aria-hidden>{String(i + 1).padStart(2, '0')}</span><p><Marks text={f} ctx={ctx} /></p></li>
            ))}
          </ol>
        </section>
      </div>

      <div className="pf-main">
        {ed.question ? (
          <section className="pf-question" aria-labelledby="q-h">
            <h2 id="q-h" className="pf-label">{s(lang, 'question')}</h2>
            <p className="pf-question__label">{s(lang, 'ourQuestion')}</p>
            <blockquote className="pf-question__asked"><p>{ed.question.asked}</p></blockquote>
            <p className="pf-question__label">{s(lang, 'lookedAt')}</p>
            <p className="pf-question__looked">{ed.question.lookedAt}</p>
            {ed.question.premiseNote ? <p className="pf-question__note"><strong>{s(lang, 'premiseNote')}.</strong> {ed.question.premiseNote}</p> : null}
          </section>
        ) : null}

        {ed.sections.map((sec, i) => (
          <section key={sec.id} id={`sec-${sec.id}`} className="pf-sec" aria-labelledby={`h-${sec.id}`}>
            <h2 id={`h-${sec.id}`} className="pf-h2"><span className="pf-h2__num">{i + 1}</span>{sec.heading}</h2>
            {sec.blocks.map((b, j) => <BlockView key={j} b={b} a={a} lang={lang} ctx={ctx} figs={figs} />)}
          </section>
        ))}

        {ed.insight?.text ? (
          <aside id="insight" className="pf-insight" aria-label={ed.insight.label ?? gt(lang, 'ourRead')}>
            <div className="pf-strata pf-strata--short" aria-hidden><span /><span /><span /></div>
            <p className="pf-insight__label">{ed.insight.label ?? gt(lang, 'ourRead')}</p>
            <p className="pf-insight__text"><Marks text={ed.insight.text} ctx={ctx} /></p>
          </aside>
        ) : null}
      </div>

      <div className="pf-end">
        {terms.length ? (
          <section id="terms" className="pf-terms" aria-labelledby="terms-h">
            <h2 id="terms-h" className="pf-h3">{s(lang, 'termsTitle')}</h2>
            <dl>
              {terms.map((x) => (
                <div key={x.id} className="pf-terms__row">
                  <dt>{tx(GLOSSARY[x.id].term, lang)}</dt>
                  <dd>{tx(GLOSSARY[x.id].definition, lang)}{x.context ? <span className="pf-terms__ctx"> {tx(x.context, lang)}</span> : null}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}

        <References a={a} lang={lang} nums={nums} />

        {a.related.length ? (
          <section className="pf-related" aria-labelledby="rel-h">
            <h2 id="rel-h" className="pf-h3">{s(lang, 'related')}</h2>
            <ul>
              {a.related.map((r, i) => (
                <li key={i}>
                  <a href={r.url} lang="en">{r.title}</a>
                  <span className="pf-muted">{[r.institution, r.date ? fmtPeriod(r.date, lang, 'auto') : null].filter(Boolean).join(' · ')}</span>
                  {r.why ? <span className="pf-related__why">{tx(r.why, lang)}</span> : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {meta.citation ? (
          <section id="cite" className="pf-cite" aria-labelledby="cite-h">
            <h2 id="cite-h" className="pf-h3">{s(lang, 'cite.title')}</h2>
            <p className="pf-cite__ask">{s(lang, 'cite.ask')}</p>
            <p className="pf-cite__text">{citationText(meta.citation, lang)}</p>
            <pre className="pf-cite__bib">{citationBibtex(meta.citation, slug, lang)}</pre>
          </section>
        ) : null}

        <footer className="pf-end">
          {meta.corrections?.length ? (
            <p className="pf-end__corr"><strong>{s(lang, 'corrections')}.</strong> {meta.corrections.map((c, i) => <span key={i}>{i ? ' ' : ''}{fmtPeriod(c.date, lang, 'auto')}: {tx(c.text, lang)}</span>)}</p>
          ) : null}
          {ed.disclaimer ? <p className="pf-end__disclaimer"><strong>{s(lang, 'disclaimer')}.</strong> {ed.disclaimer}</p> : null}
          <p className="pf-end__pdf">{s(lang, 'print.made', { date: made })}</p>
        </footer>
      </div>
    </article>
  );
}

function BlockView({ b, a, lang, ctx, figs }: { b: Block; a: Article; lang: Lang; ctx: MarkCtx; figs: Map<string, number> }) {
  if (b.type === 'p') return <p className="pf-p"><Marks text={b.text} ctx={ctx} /></p>;
  if (b.type === 'list') return <ul className="pf-list">{b.items.map((x, i) => <li key={i}><Marks text={x} ctx={ctx} /></li>)}</ul>;
  if (b.type === 'quote') {
    const src = b.cite ? ctx.sources.get(b.cite) : undefined;
    return (
      <blockquote className="pf-quote" lang={src?.quote?.lang ?? 'en'}>
        <p>“{b.text}”</p>
        {src ? <footer>— {src.institution ?? src.series}{src.date ? `, ${src.date.slice(0, 4)}` : ''}{'\u2060'}<Cites ids={[src.id]} ctx={ctx} /></footer> : null}
      </blockquote>
    );
  }
  if (b.type === 'table') {
    return (
      <div className="pf-tableblock">
        <table className="pf-table">
          {b.caption ? <caption>{b.caption}{b.source ? <Cites ids={[b.source]} ctx={ctx} /> : null}</caption> : null}
          <thead><tr>{b.columns.map((c) => <th key={c.key} scope="col" className={c.align === 'right' ? 'is-num' : undefined}>{c.label}</th>)}</tr></thead>
          <tbody>
            {b.rows.map((r, i) => <tr key={i}>{b.columns.map((c, j) => (j === 0
              ? <th key={c.key} scope="row" className={c.align === 'right' ? 'is-num' : undefined}>{r[c.key]}</th>
              : <td key={c.key} className={c.align === 'right' ? 'is-num' : undefined}>{r[c.key]}</td>))}</tr>)}
          </tbody>
        </table>
      </div>
    );
  }
  if (b.type === 'figure') {
    const spec = a.charts[b.chart];
    return spec ? <PrintFigure spec={spec} n={figs.get(b.chart) ?? 0} lang={lang} ctx={ctx} /> : null;
  }
  return null;
}

/** A figure for paper: the plot drawn at the column's width (no chart/table switch, tooltips or downloads), the
 *  takeaway above it and the notes and source under it. A table-form figure prints its table. */
function PrintFigure({ spec, n, lang, ctx }: { spec: ChartSpec; n: number; lang: Lang; ctx: MarkCtx }) {
  const m = spec.meta ?? {};
  const srcIds = m.sources ?? [];
  const last = m.lastObservation ? fmtPeriod(m.lastObservation, lang, 'auto') : null;
  const source = sourceLine(tx(m.attribution, lang), lang); // "Source: …" / "자료: …", head never doubled
  const plot = spec.form === 'line' ? <LineChart spec={spec} lang={lang} height={250} />
    : spec.form === 'bars' ? <BarChart spec={spec} lang={lang} />
    : spec.form === 'dumbbell' ? <DumbbellChart spec={spec} lang={lang} />
    : spec.form === 'scatter' ? <ScatterChart spec={spec} lang={lang} height={280} />
    : spec.form === 'stat-tiles' ? <StatTiles tiles={spec.tiles ?? []} lang={lang} renderCite={(ids) => <Cites ids={ids} ctx={ctx} />} />
    : spec.form === 'table' ? <SpecTable spec={spec} lang={lang} />
    : null;
  return (
    <figure id={`fig-${spec.id}`} data-chart={spec.id} data-form={spec.form} className={`pf-fig pf-fig--${spec.form}`} lang={lang}>
      <div className="pf-fig__head">
        <p className="pf-fig__num">{s(lang, 'figure', { n })}</p>
        {spec.headline ? <p className="pf-fig__headline">{tx(spec.headline, lang)}</p> : null}
        <p className="pf-fig__title">{tx(spec.title, lang)}{spec.subtitle ? <span className="pf-fig__sub"> · {tx(spec.subtitle, lang)}</span> : null}</p>
      </div>
      <div className="pf-fig__body" role={spec.form === 'stat-tiles' ? 'img' : undefined} aria-label={spec.form === 'stat-tiles' ? tx(spec.alt, lang) : undefined}>{plot}</div>
      <figcaption className="pf-fig__foot">
        {spec.howToRead ? <p><span className="pf-fig__how">{s(lang, 'howToRead')}.</span> {tx(spec.howToRead, lang)}</p> : null}
        {(spec.notes ?? []).map((x, i) => <p key={i}>{tx(x, lang)}</p>)}
        <p className="pf-fig__source">
          {source ? <><span className="pf-fig__how">{source.slice(0, source.indexOf(':') + 1)}</span> {source.slice(source.indexOf(':') + 2)}</> : null}
          {last ? <span>{' · '}{s(lang, 'dataTo', { date: last })}</span> : null}
          {srcIds.length ? <Cites ids={srcIds} ctx={ctx} /> : null}
        </p>
      </figcaption>
    </figure>
  );
}

/** A table-form figure: the chart's own table (contracts/chart.schema.json `table`), numbers by locale. */
function SpecTable({ spec, lang }: { spec: ChartSpec; lang: Lang }) {
  const t = spec.table;
  if (!t) return null;
  const cell = (v: unknown, decimals?: number) => (v == null ? '–' : typeof v === 'number' ? fmt(v, lang, { decimals: decimals ?? (Number.isInteger(v) ? 0 : 1) })
    : typeof v === 'object' ? tx(v as { en: string; ko?: string }, lang) : String(v));
  return (
    <table className="pf-table">
      <thead><tr>{t.columns.map((c) => <th key={c.key} scope="col" className={c.align === 'right' ? 'is-num' : undefined}>{tx(c.label, lang)}</th>)}</tr></thead>
      <tbody>
        {t.rows.map((r, i) => (
          <tr key={i}>{t.columns.map((c, j) => (j === 0
            ? <th key={c.key} scope="row" className={c.align === 'right' ? 'is-num' : undefined}>{cell(r[c.key], c.decimals)}</th>
            : <td key={c.key} className={c.align === 'right' ? 'is-num' : undefined}>{cell(r[c.key], c.decimals)}</td>))}</tr>
        ))}
      </tbody>
    </table>
  );
}

/** Numbered references, grouped as on the web page, each with the address a reader of the paper can type. How to find
 *  each data series on its provider's site is left to the online version: it runs to pages on paper. */
function References({ a, lang, nums }: { a: Article; lang: Lang; nums: Map<string, number> }) {
  const sorted = [...a.sources].sort((x, y) => (nums.get(x.id) ?? 0) - (nums.get(y.id) ?? 0));
  const groups = GROUPS.map((g) => ({ ...g, items: sorted.filter((x) => g.kinds.includes(x.kind)) })).filter((g) => g.items.length);
  const other = sorted.filter((x) => !GROUPS.some((g) => g.kinds.includes(x.kind)));
  if (other.length) groups.push({ key: 'ref.other', kinds: [], items: other });
  return (
    <section id="references" className="pf-refs" aria-labelledby="refs-h">
      <h2 id="refs-h" className="pf-h3">{s(lang, 'references')}</h2>
      {groups.map((g) => (
        <div key={g.key} className="pf-refs__group">
          <h3 className="pf-label">{s(lang, g.key)}</h3>
          <ol>
            {g.items.map((src) => {
              const link = src.doi ? `https://doi.org/${src.doi}` : src.url ?? src.pdfUrl;
              return (
                <li key={src.id} id={`ref-${src.id}`}>
                  <span className="pf-refs__num">{nums.get(src.id)}</span>
                  <div>
                    <p className="pf-refs__cite">{src.cite ? tx(src.cite, lang) : src.title}</p>
                    {src.titleTranslated?.[lang] ? <p className="pf-refs__tr">{src.titleTranslated[lang]}</p> : null}
                    {link ? <p className="pf-refs__url"><a href={link}>{link.replace(/^https?:\/\//, '')}</a></p> : null}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </section>
  );
}
