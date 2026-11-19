import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ArticleHeader, Button, Insight, KeyFindings, Notice, Tag } from '@glacier/ui';
import { LANGS, t as gt, type Lang } from '@glacier/i18n';
import { StatTiles, fmtPeriod, tx } from '@articles/charts';
import { Figure } from '@/components/Figure';
import { CiteBlock } from '@/components/CiteBlock';
import { CopyButton } from '@/components/CopyButton';
import { PdfButton } from '@/components/PdfLink';
import { Cites, Marks, type MarkCtx } from '@/components/Marks';
import { Toc, type TocItem } from '@/components/Toc';
import { ARTICLES, GLOSSARY, editionOf, editionsOf, getArticle, getPipeline, type Article, type Block, type Reproduce, type Source } from '@/lib/content';
import { citations, figureNumbers, type Place } from '@/lib/cites';
import { langOf } from '@/lib/page';
import { s } from '@/lib/strings';

type Params = Promise<{ lang: string; slug: string }>;
export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.flatMap((lang) => ARTICLES.map((a) => ({ lang, slug: a.slug })));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { slug } = await params;
  const lang = await langOf(params);
  const a = getArticle(slug);
  if (!a) return {};
  const { ed, fallback } = editionOf(a, lang);
  const pdfUrl = a.meta.pdf?.[lang]?.url;
  const description = ed.dek.replace(/\[\[[^\]]*\]\]|\(\(([^)|]+)\|?([^)]*)\)\)/g, (_, id, text) => text || id || '');
  const langs = editionsOf(a);
  return {
    title: ed.title,
    description,
    alternates: {
      // A language the article lacks shows the other edition; its canonical names that edition, so it is no duplicate.
      canonical: `/${fallback ? langs[0] : lang}/a/${slug}`,
      languages: { ...Object.fromEntries(langs.map((l) => [l, `/${l}/a/${slug}`])), 'x-default': `/a/${slug}` },
      ...(pdfUrl ? { types: { 'application/pdf': pdfUrl } } : {}),
    },
    openGraph: { type: 'article', locale: lang === 'ko' ? 'ko_KR' : 'en_GB', title: ed.title, description, url: `/${lang}/a/${slug}`, publishedTime: a.meta.date },
    // The picture comes from opengraph-image.tsx beside this page; X shows it full width with this card.
    twitter: { card: 'summary_large_image', title: ed.title, description },
  };
}

const GROUPS: Array<{ key: 'ref.research' | 'ref.speeches' | 'ref.data' | 'ref.other'; kinds: Source['kind'][] }> = [
  { key: 'ref.research', kinds: ['paper', 'policy-note', 'report'] },
  { key: 'ref.speeches', kinds: ['speech', 'web'] },
  { key: 'ref.data', kinds: ['dataset'] },
];

export default async function ArticlePage({ params }: { params: Params }) {
  const { slug } = await params;
  const pageLang = await langOf(params);
  const a = getArticle(slug);
  if (!a) notFound();
  const { ed, lang, fallback } = editionOf(a, pageLang);
  const { nums, places } = citations(a, ed, { keyNumbers: s(lang, 'keyNumbers'), findings: s(lang, 'findingsTitle'), insight: ed.insight?.label ?? gt(lang, 'ourRead') });
  const figs = figureNumbers(ed);
  const ctx: MarkCtx = { lang, nums, sources: new Map(a.sources.map((x) => [x.id, x])), glossary: GLOSSARY, termContext: new Map(a.terms.map((x) => [x.id, x.context])) };
  const meta = a.meta;
  const type = getPipeline(meta.type);
  const terms = a.terms.filter((x) => GLOSSARY[x.id]);
  const approved = Boolean(meta.review?.approved);
  const readTime = meta.readTime?.[lang];
  const pdf = meta.pdf?.[lang];
  const block = (b: Block, i: number) => <BlockView key={i} b={b} a={a} lang={lang} ctx={ctx} figs={figs} />;
  const plain = (x: string) => x.replace(/\s*\[\[[^\]]*\]\]/g, '').replace(/\(\(([^)|]+)(?:\|([^)]*))?\)\)/g, (_m: string, id: string, text: string) => text || id).replace(/\*([^*]+)\*/g, '$1');
  const toc: TocItem[] = [
    { id: 'findings', label: s(lang, 'findingsTitle'), summary: s(lang, 'toc.findings') },
    ...(ed.question ? [{ id: 'q-h', label: s(lang, 'question'), summary: s(lang, 'toc.question') }] : []),
    ...ed.sections.map((sec) => ({ id: `sec-${sec.id}`, label: sec.heading, summary: sec.summary ? plain(sec.summary) : null })),
    ...(ed.insight?.text ? [{ id: 'insight', label: ed.insight.label ?? gt(lang, 'ourRead'), summary: s(lang, 'toc.insight') }] : []),
    ...(terms.length ? [{ id: 'terms', label: s(lang, 'termsTitle'), summary: s(lang, 'toc.terms') }] : []),
    ...(ed.reproduce?.items?.length ? [{ id: 'get-data', label: ed.reproduce.heading, summary: null }] : []),
    { id: 'references', label: s(lang, 'references'), summary: s(lang, 'toc.references') },
    ...(meta.citation ? [{ id: 'cite', label: s(lang, 'cite.title'), summary: s(lang, 'toc.cite') }] : []),
  ];

  return (
    <article className="article" lang={lang}>
      <Toc items={toc} title={s(lang, 'toc')} />
      {!approved ? (
        <div className="ac-narrow ac-preview"><Notice lang={lang} tone="warning" title={s(lang, 'previewTitle')}>{s(lang, 'previewBody')}</Notice></div>
      ) : null}
      {fallback ? (
        <div className="ac-narrow ac-preview"><Notice lang={pageLang} tone="info" title={pageLang === 'ko' ? '이 글은 아직 영어로만 제공됩니다' : 'This piece is only available in Korean for now'}>{pageLang === 'ko' ? '번역이 준비되면 이 페이지에 게시합니다.' : 'The translation will appear on this page when it is ready.'}</Notice></div>
      ) : null}
      <ArticleHeader
        lang={lang}
        kicker={ed.kicker}
        title={ed.title}
        subtitle={ed.dek.replace(/\s*\[\[[^\]]*\]\]/g, '').replace(/\(\(([^)|]+)(?:\|([^)]*))?\)\)/g, (_m: string, id: string, text: string) => text || id).replace(/\*([^*]+)\*/g, '$1')}
        author={ed.byline ?? 'datasteg'}
        authorInitials="ds"
        readTime={readTime ? gt(lang, 'readTime', { n: readTime }) : undefined}
        date={fmtPeriod(meta.date, lang, 'auto')}
        leading={(
          <span className="gl-tags">
            {type ? <Tag className="tag-format" href={`/${lang}/formats/${type.id}`}>{tx(type.name, lang)}</Tag> : null}
            {meta.topics.map((x) => <Tag key={x.id} href={`/${lang}?topic=${x.id}`}>{tx(x.label, lang)}</Tag>)}
          </span>
        )}
        actions={meta.citation || pdf ? (
          <>
            {pdf ? <PdfButton pdf={pdf} slug={a.slug} lang={lang} /> : null}
            {meta.citation ? <Button size="sm" href="#cite">{s(lang, 'cite.button')}</Button> : null}
          </>
        ) : null}
      />

      {ed.whyNow ? (
        <p className="ac-narrow ac-why"><strong>{ed.whyNowLabel ?? 'Why this note'}.</strong> <Marks text={ed.whyNow} ctx={ctx} /></p>
      ) : null}
      {ed.keyNumbers?.length ? (
        <section id="key-numbers" className="ac-narrow ac-keynums" aria-label={s(lang, 'keyNumbers')}>
          <h2 className="gl-kicker gl-kicker--muted">{s(lang, 'keyNumbers')}</h2>
          <StatTiles lang={lang} tiles={ed.keyNumbers.map((k) => ({ value: k.value, label: k.label, cite: k.cite }))} renderCite={(ids) => <Cites ids={ids} ctx={ctx} />} />
        </section>
      ) : null}

      <div id="findings">
        <KeyFindings lang={lang} title={s(lang, 'findingsTitle')} items={ed.findings.map((f, i) => <Marks key={i} text={f} ctx={ctx} />)} />
      </div>

      {ed.question ? (
        <section className="ac-narrow ac-question" aria-labelledby="q-h">
          <h2 id="q-h" className="ac-question__h">{s(lang, 'question')}</h2>
          <div className="ac-question__box">
            <p className="ac-question__label">{s(lang, 'ourQuestion')}</p>
            <blockquote className="ac-question__asked"><p>{ed.question.asked}</p></blockquote>
            <p className="ac-question__label">{s(lang, 'lookedAt')}</p>
            <p className="ac-question__looked">{ed.question.lookedAt}</p>
            {ed.question.premiseNote ? (
              <p className="ac-question__note">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" aria-hidden><path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" /><path d="M12 11v5" /><path d="M12 7.6v.1" /></svg>
                <span><strong>{s(lang, 'premiseNote')}.</strong> {ed.question.premiseNote}</span>
              </p>
            ) : null}
          </div>
        </section>
      ) : null}

      {ed.sections.map((sec) => (
        <section key={sec.id} id={`sec-${sec.id}`} className="ac-section" aria-labelledby={`h-${sec.id}`}>
          <div className="gl-prose"><h2 id={`h-${sec.id}`}>{sec.heading}</h2></div>
          {sec.blocks.map(block)}
        </section>
      ))}

      {ed.insight?.text ? (
        <div id="insight">
          <Insight lang={lang} label={ed.insight.label}><p><Marks text={ed.insight.text} ctx={ctx} /></p></Insight>
        </div>
      ) : null}

      {terms.length ? (
        <section className="ac-narrow ac-terms" aria-labelledby="terms-h" id="terms">
          <h2 id="terms-h" className="ac-h2">{s(lang, 'termsTitle')}</h2>
          <dl>
            {terms.map((x) => {
              const g = GLOSSARY[x.id];
              return (
                <div key={x.id} className="ac-terms__row">
                  <dt><a href={`/${lang}/glossary/${x.id}`}>{tx(g.term, lang)}</a></dt>
                  <dd>
                    {tx(g.definition, lang)}
                    {x.context ? <span className="ac-terms__ctx">{tx(x.context, lang)}</span> : null}
                  </dd>
                </div>
              );
            })}
          </dl>
        </section>
      ) : null}

      {ed.reproduce?.items?.length ? <GetData r={ed.reproduce} lang={lang} zip={meta.download?.url ? { url: meta.download.url, bytes: meta.download.bytes, name: `datasteg-${a.slug}-data.zip` } : null} /> : null}

      <References a={a} lang={lang} ctx={ctx} places={places} />

      {a.related.length ? (
        <section className="ac-narrow ac-related" aria-labelledby="rel-h">
          <h2 id="rel-h" className="ac-h2">{s(lang, 'related')}</h2>
          <ul>
            {a.related.map((r, i) => (
              <li key={i}>
                <a className="gl-link" href={r.url} target="_blank" rel="noopener" lang="en">{r.title}</a>
                <span className="ac-related__meta">{[r.institution, r.date ? fmtPeriod(r.date, lang, 'auto') : null].filter(Boolean).join(' · ')}</span>
                {r.why ? <span className="ac-related__why">{tx(r.why, lang)}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {meta.citation ? <CiteBlock citation={meta.citation} slug={a.slug} lang={lang} pdf={meta.pdf} /> : null}

      <footer className="ac-narrow ac-end">
        {meta.corrections?.length ? (
          <section className="ac-end__corrections" aria-labelledby="corr-h">
            <h2 id="corr-h" className="ac-end__h">{s(lang, 'corrections')}</h2>
            <ul>{meta.corrections.map((c, i) => <li key={i}><span className="ac-mono">{c.date}</span> {tx(c.text, lang)}</li>)}</ul>
          </section>
        ) : null}
        {ed.disclaimer ? <p className="ac-end__disclaimer"><strong>{s(lang, 'disclaimer')}.</strong> {ed.disclaimer}</p> : null}
      </footer>
    </article>
  );
}

/** "Get the data": the pages to explore and the API calls that return the same tables (data notes only). */
function GetData({ r, lang, zip }: { r: Reproduce; lang: Lang; zip: { url: string; bytes: number; name: string } | null }) {
  return (
    <section className="ac-narrow ac-getdata" aria-labelledby="get-data-h" id="get-data">
      <h2 id="get-data-h" className="ac-h2">{r.heading}</h2>
      <p className="ac-getdata__intro">{r.intro}</p>
      <ul>
        {r.items.map((i, k) => (
          <li key={k}>
            {i.page ? <a className="gl-link" href={i.page} target="_blank" rel="noopener">{i.label}</a> : <span>{i.label}</span>}
            <span className="ac-getdata__app">{i.app}</span>
            <code className="ac-getdata__api" lang="en">{i.api}</code>
          </li>
        ))}
      </ul>
      {zip && r.download ? (
        <p className="ac-getdata__zip">
          <a className="gl-btn gl-btn--secondary gl-btn--sm" href={zip.url} download={zip.name} type="application/zip">{r.download.label}</a>
          <span className="ac-getdata__size" lang="en">ZIP · {zip.bytes < 1e6 ? `${Math.max(1, Math.round(zip.bytes / 1024))} KB` : `${(zip.bytes / 1e6).toFixed(1)} MB`}</span>
        </p>
      ) : null}
      {r.code ? (
        <div className="ac-getdata__code">
          <pre lang="en"><code>{r.code}</code></pre>
          <CopyButton text={r.code} label={s(lang, 'cite.copy')} done={s(lang, 'cite.copied')} />
        </div>
      ) : null}
      {r.note || r.docs ? (
        <p className="ac-getdata__note">
          {r.note}{r.note && r.docs ? ' ' : ''}
          {r.docs ? <a className="gl-link" href={r.docs} target="_blank" rel="noopener" lang="en">api.datasteg.com</a> : null}
        </p>
      ) : null}
    </section>
  );
}

function BlockView({ b, a, lang, ctx, figs }: { b: Block; a: Article; lang: Lang; ctx: MarkCtx; figs: Map<string, number> }) {
  if (b.type === 'p') return <div className="gl-prose"><p><Marks text={b.text} ctx={ctx} /></p></div>;
  if (b.type === 'list') return <div className="gl-prose"><ul>{b.items.map((x, i) => <li key={i}><Marks text={x} ctx={ctx} /></li>)}</ul></div>;
  if (b.type === 'quote') {
    const src = b.cite ? ctx.sources.get(b.cite) : undefined;
    return (
      <div className="gl-prose">
        <blockquote className="ac-quote" lang={src?.quote?.lang ?? 'en'}>
          <p>“{b.text}”</p>
          {src ? <footer>— {src.institution ?? src.series}{src.date ? `, ${src.date.slice(0, 4)}` : ''}{'\u2060'}<Cites ids={[src.id]} ctx={ctx} /></footer> : null}
        </blockquote>
      </div>
    );
  }
  if (b.type === 'table') {
    return (
      <div className="ac-narrow ac-tableblock">
        <div className="gl-table-wrap" tabIndex={0} role="region" aria-label={b.caption}>
          <table className="gl-table gl-table--dense">
            {b.caption ? <caption className="gl-table__caption">{b.caption}{b.source ? <Cites ids={[b.source]} ctx={ctx} /> : null}</caption> : null}
            <thead><tr>{b.columns.map((c) => <th key={c.key} scope="col" className={c.align === 'right' ? 'is-num' : undefined}>{c.label}</th>)}</tr></thead>
            <tbody>
              {b.rows.map((r, i) => (
                <tr key={i}>{b.columns.map((c, j) => (j === 0
                  ? <th key={c.key} scope="row" className={c.align === 'right' ? 'is-num' : undefined}>{r[c.key]}</th>
                  : <td key={c.key} className={c.align === 'right' ? 'is-num' : undefined}>{r[c.key]}</td>))}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  if (b.type === 'figure') {
    const spec = a.charts[b.chart];
    if (!spec) return null;
    return <Figure spec={spec} n={figs.get(b.chart) ?? 0} lang={lang} ctx={ctx} />;
  }
  return null;
}

function References({ a, lang, ctx, places }: { a: Article; lang: Lang; ctx: MarkCtx; places: Map<string, Place[]> }) {
  const sorted = [...a.sources].sort((x, y) => (ctx.nums.get(x.id) ?? 0) - (ctx.nums.get(y.id) ?? 0));
  const groups = GROUPS.map((g) => ({ ...g, items: sorted.filter((x) => g.kinds.includes(x.kind)) })).filter((g) => g.items.length);
  const other = sorted.filter((x) => !GROUPS.some((g) => g.kinds.includes(x.kind)));
  if (other.length) groups.push({ key: 'ref.other', kinds: [], items: other });
  return (
    <section className="ac-narrow ac-refs" aria-labelledby="refs-h" id="references">
      <h2 id="refs-h" className="ac-h2">{s(lang, 'references')}</h2>
      {groups.map((g) => (
        <div key={g.key} className="ac-refs__group">
          <h3 className="gl-kicker gl-kicker--muted">{s(lang, g.key)}</h3>
          <ol className="ac-refs__list">
            {g.items.map((src) => {
              const where = places.get(src.id) ?? [];
              return (
                <li key={src.id} id={`ref-${src.id}`} className="ac-ref">
                  <span className="ac-ref__num">{ctx.nums.get(src.id)}</span>
                  <div>
                    <p className="ac-ref__cite">{src.cite ? tx(src.cite, lang) : src.title}</p>
                    {src.titleTranslated?.[lang] ? <p className="ac-ref__tr">{src.titleTranslated[lang]}</p> : null}
                    {src.kind === 'dataset' && src.dataset?.locate ? (
                      <p className="ac-ref__how"><strong>{s(lang, 'findSeries')}:</strong> {tx(src.dataset.locate, lang)}</p>
                    ) : null}
                    <p className="ac-ref__links">
                      {src.url ? <a href={src.url} target="_blank" rel="noopener">{s(lang, src.kind === 'dataset' ? 'dataSource' : 'readSource')} ↗</a> : null}
                      {src.pdfUrl ? <a href={src.pdfUrl} target="_blank" rel="noopener">PDF ↗</a> : null}
                      {src.doi ? <a href={`https://doi.org/${src.doi}`} target="_blank" rel="noopener" className="ac-mono">doi:{src.doi}</a> : null}
                      {where.length ? (
                        <span className="ac-ref__back">{s(lang, 'citedIn')}: {where.map((p, i) => <span key={p.anchor}>{i ? ', ' : ''}<a href={`#${p.anchor}`}>↑ {p.label}</a></span>)}</span>
                      ) : null}
                    </p>
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
