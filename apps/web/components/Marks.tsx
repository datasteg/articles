import { Fragment, type ReactNode } from 'react';
import type { Lang } from '@glacier/i18n';
import { fmtPeriod, tx } from '@articles/charts';
import type { GlossaryTerm, Source, Txt } from '@/lib/content';
import { s } from '@/lib/strings';
import { Popover } from './Popover';

/** What inline marks need: citation numbers, the sources, the glossary, and how this article uses each term.
 *  `print` (the PDF edition) draws citations as plain numbers linked to the references and terms as plain text. */
export interface MarkCtx { lang: Lang; nums: Map<string, number>; sources: Map<string, Source>; glossary: Record<string, GlossaryTerm>; termContext?: Map<string, Txt | null | undefined>; print?: boolean }

const MARK = /\[\[([^\]]+)\]\]|\(\(([^)|]+)(?:\|([^)]+))?\)\)|\*([^*\n]+)\*|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;

/** Text with [[S1,S2]] citations, ((term|text)) glossary marks, *emphasis* and [links](https://…)
 *  (contracts/content.md). Whitespace before a citation is dropped so the superscript sits on the word. */
export function Marks({ text, ctx }: { text: string; ctx: MarkCtx }) {
  const out: ReactNode[] = [];
  let last = 0, k = 0;
  const push = (n: ReactNode) => out.push(<Fragment key={k++}>{n}</Fragment>);
  for (const m of text.matchAll(MARK)) {
    if ((m.index ?? 0) < last) continue; // already merged into the previous citation group
    let before = text.slice(last, m.index);
    if (m[1]) before = before.replace(/\s+$/, '') + '\u2060'; // word joiner: the superscript never wraps alone
    if (before) push(before);
    last = (m.index ?? 0) + m[0].length;
    if (m[1]) {
      // merge adjacent citations "[[S5]] [[S7]]" into one group
      const ids = m[1].split(',').map((x) => x.trim());
      const next = /^\s*\[\[([^\]]+)\]\]/.exec(text.slice(last));
      if (next) { ids.push(...next[1].split(',').map((x) => x.trim())); last += next[0].length; }
      push(<Cites ids={ids} ctx={ctx} />);
    } else if (m[2]) {
      push(<Term id={m[2].trim()} text={m[3]} ctx={ctx} />);
    } else if (m[4]) {
      push(<em>{m[4]}</em>);
    } else if (m[5]) {
      push(<a className="gl-link" href={m[6]} target="_blank" rel="noopener">{m[5]}</a>);
    }
  }
  if (last < text.length) push(text.slice(last));
  return <>{out}</>;
}

export function Cites({ ids, ctx }: { ids: string[]; ctx: MarkCtx }) {
  const known = [...new Set(ids)].filter((id) => ctx.sources.has(id)).sort((a, b) => (ctx.nums.get(a) ?? 0) - (ctx.nums.get(b) ?? 0));
  if (!known.length) return null;
  if (ctx.print) {
    return (
      <sup className="ac-sup">
        {known.map((id, i) => <Fragment key={id}>{i ? <span className="ac-sup__sep">,</span> : null}<a href={`#ref-${id}`}>{ctx.nums.get(id)}</a></Fragment>)}
      </sup>
    );
  }
  return (
    <sup className="ac-sup">
      {known.map((id, i) => {
        const src = ctx.sources.get(id) as Source;
        const n = ctx.nums.get(id) ?? 0;
        return (
          <Fragment key={id}>
            {i ? <span className="ac-sup__sep" aria-hidden>,</span> : null}
            <Popover href={`#ref-${id}`} className="ac-cite" label={`${s(ctx.lang, 'source')} ${n}: ${src.title}`} closeLabel={s(ctx.lang, 'close')}
              popClass="ac-pop--source" trigger={<><span className="gl-visually-hidden">{s(ctx.lang, 'source')} </span>{n}</>}>
              <SourceCard src={src} n={n} lang={ctx.lang} />
            </Popover>
          </Fragment>
        );
      })}
    </sup>
  );
}

function Term({ id, text, ctx }: { id: string; text?: string; ctx: MarkCtx }) {
  const g = ctx.glossary[id];
  const shown = text ?? (g ? tx(g.term, ctx.lang) : id);
  if (!g || ctx.print) return <>{shown}</>;
  const here = ctx.termContext?.get(id);
  const href = `/${ctx.lang}/glossary/${id}`;
  return (
    <Popover href={href} className="ac-term" label={tx(g.term, ctx.lang)} closeLabel={s(ctx.lang, 'close')} popClass="ac-pop--term" trigger={shown}>
      <p className="ac-pop__kicker">{s(ctx.lang, 'glossaryTitle')}</p>
      <p className="ac-pop__title">{tx(g.term, ctx.lang)}</p>
      <p className="ac-pop__body">{tx(g.definition, ctx.lang)}</p>
      {here ? <p className="ac-pop__used">{tx(here, ctx.lang)}</p> : null}
      <p className="ac-pop__links"><a href={href}>{s(ctx.lang, 'term.more')} →</a></p>
    </Popover>
  );
}

/** What a source popover shows: where it's from, the title, the verified quote, what we used it for, links. */
export function SourceCard({ src, n, lang }: { src: Source; n: number; lang: Lang }) {
  const when = src.date ? fmtPeriod(src.date, lang, 'auto') : null;
  const venue = [src.series ?? src.institution, src.number].filter(Boolean).join(' ');
  const tr = src.titleTranslated?.[lang];
  const d = src.dataset;
  return (
    <>
      <p className="ac-pop__kicker"><span className="ac-pop__num">{n}</span>{[venue, when].filter(Boolean).join(' · ')}</p>
      <p className="ac-pop__title" lang={src.kind === 'dataset' ? undefined : 'en'}>{src.title}</p>
      {tr ? <p className="ac-pop__title-tr">{tr}</p> : null}
      {src.quote?.text ? (
        <blockquote className="ac-pop__quote" lang={src.quote.lang ?? 'en'}>
          <p>“{src.quote.text}”</p>
          {src.quote.locator ? <footer>{src.quote.locator}</footer> : null}
        </blockquote>
      ) : null}
      {d ? (
        <dl className="ac-pop__facts">
          {d.provider ? <><dt>{s(lang, 'provider')}</dt><dd>{d.provider}</dd></> : null}
          {d.key ? <><dt>{s(lang, 'seriesKey')}</dt><dd className="ac-mono">{d.key}</dd></> : null}
          {d.unit ? <><dt>{s(lang, 'unit')}</dt><dd>{d.unit}</dd></> : null}
          {d.frequency ? <><dt>{s(lang, 'frequency')}</dt><dd>{d.frequency}</dd></> : null}
          {d.lastObservation ? <><dt>{s(lang, 'lastObservation')}</dt><dd>{fmtPeriod(d.lastObservation, lang, 'auto')}</dd></> : null}
          {d.retrieved ? <><dt>{s(lang, 'retrieved')}</dt><dd>{fmtPeriod(d.retrieved, lang, 'auto')}</dd></> : null}

        </dl>
      ) : null}
      {src.usedFor ? <p className="ac-pop__used"><span>{s(lang, 'usedFor')}:</span> {tx(src.usedFor, lang)}</p> : null}
      <p className="ac-pop__links">
        {src.url ? <a href={src.url} target="_blank" rel="noopener">{s(lang, src.kind === 'dataset' ? 'dataSource' : 'readSource')} ↗</a> : null}
        {src.pdfUrl ? <a href={src.pdfUrl} target="_blank" rel="noopener">{s(lang, 'openPdf')} ↗</a> : null}
        <a href={`#ref-${src.id}`}>{s(lang, 'allRefs')} ↓</a>
      </p>
    </>
  );
}
