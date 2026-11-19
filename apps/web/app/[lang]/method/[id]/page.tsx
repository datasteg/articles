import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { Notice } from '@glacier/ui';
import { LANGS } from '@glacier/i18n';
import { tx } from '@articles/charts';
import { PipelineDiagram, pipelineCounts } from '@/components/PipelineDiagram';
import { PIPELINES, articlesOfType, getPipeline, plural } from '@/lib/content';
import { langOf } from '@/lib/page';
import { s } from '@/lib/strings';

type Params = Promise<{ lang: string; id: string }>;
export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.flatMap((lang) => PIPELINES.map((p) => ({ lang, id: p.id })));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const lang = await langOf(params);
  const p = getPipeline(id);
  return p ? { title: s(lang, 'method.titleType', { name: plural(p, lang) }), description: tx(p.tagline, lang) } : {};
}

/** How one format is made: its shape, then its pipeline as a diagram (config/pipelines/<id>.yaml). */
export default async function MethodType({ params }: { params: Params }) {
  const { id } = await params;
  const lang = await langOf(params);
  const p = getPipeline(id);
  if (!p) notFound();
  const c = pipelineCounts(p);
  const n = articlesOfType(p.id).length;
  const facts = [
    { label: s(lang, 'shape.length'), value: p.shape?.words ? tx(p.shape.words, lang) : '—' },
    { label: s(lang, 'shape.figures'), value: p.shape?.figures ?? '—' },
    { label: s(lang, 'shape.steps'), value: String(c.steps) },
    { label: s(lang, 'shape.gates'), value: String(p.shape?.gates ?? c.gates) },
  ];
  return (
    <>
      <header className="page-head">
        <p className="gl-kicker"><a className="page-head__up" href={`/${lang}/method`}>{s(lang, 'nav.method')}</a></p>
        <h1>{s(lang, 'method.titleType', { name: plural(p, lang) })}</h1>
        <p className="dek">{tx(p.tagline, lang)}</p>
      </header>
      {p.status !== 'live' ? <div className="page-note"><Notice lang={lang} tone="info" title={s(lang, 'format.sample')}>{s(lang, 'format.sampleNote')}</Notice></div> : null}
      <dl className="shape">
        {facts.map((f) => <div key={f.label} className="shape__item"><dt>{f.label}</dt><dd>{f.value}</dd></div>)}
      </dl>
      <div className="wide-block">
        <PipelineDiagram p={p} lang={lang} details />
      </div>
      {n ? <p className="page-more"><a className="gl-link" href={`/${lang}/formats/${p.id}`}>{s(lang, 'format.see', { name: plural(p, lang) })} →</a></p> : null}
    </>
  );
}
