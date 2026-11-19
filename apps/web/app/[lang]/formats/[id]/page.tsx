import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { EmptyState, Notice, StoryCard } from '@glacier/ui';
import { LANGS, t } from '@glacier/i18n';
import { fmtPeriod, tx } from '@articles/charts';
import { Cover } from '@/components/Cover';
import { PipelineStrip } from '@/components/PipelineDiagram';
import { PIPELINES, articlesOfType, editionOf, getPipeline, plural } from '@/lib/content';
import { langOf } from '@/lib/page';
import { s } from '@/lib/strings';
import { plainText } from '@/lib/text';

type Params = Promise<{ lang: string; id: string }>;
export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.flatMap((lang) => PIPELINES.map((p) => ({ lang, id: p.id })));
}

const capital = (x: string) => x.charAt(0).toUpperCase() + x.slice(1);

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const lang = await langOf(params);
  const p = getPipeline(id);
  return p ? { title: capital(plural(p, lang)), description: tx(p.tagline, lang) } : {};
}

/** One format's articles, with its pipeline's fingerprint linking to how it is made. */
export default async function Format({ params }: { params: Params }) {
  const { id } = await params;
  const lang = await langOf(params);
  const p = getPipeline(id);
  if (!p) notFound();
  const list = articlesOfType(p.id);
  return (
    <>
      <header className="page-head">
        <p className="gl-kicker">{s(lang, 'format.kicker')}</p>
        <h1>{capital(plural(p, lang))}</h1>
        <p className="dek">{tx(p.tagline, lang)}</p>
        <a className="format-how" href={`/${lang}/method/${p.id}`}>
          <PipelineStrip p={p} lang={lang} />
          <span>{s(lang, 'format.how', { name: plural(p, lang) })} →</span>
        </a>
      </header>
      {p.status !== 'live' ? <div className="page-note"><Notice lang={lang} tone="info" title={s(lang, 'format.sample')}>{s(lang, 'format.sampleNote')}</Notice></div> : null}
      <div className="feed-block">
        {list.length ? list.map((a) => {
          const { ed } = editionOf(a, lang);
          const rt = a.meta.readTime?.[lang];
          return (
            <StoryCard key={a.slug} lang={lang} kicker={ed.kicker} title={ed.title} dek={plainText(ed.dek)} href={`/${lang}/a/${a.slug}`}
              date={fmtPeriod(a.meta.date, lang, 'auto')} readTime={rt ? t(lang, 'readTime', { n: rt }) : undefined}
              thumbnail={a.cover ? <Cover article={a} lang={lang} /> : undefined} />
          );
        }) : <EmptyState lang={lang} title={s(lang, 'format.empty', { name: plural(p, lang) })} body={s(lang, 'format.emptyBody')} />}
      </div>
    </>
  );
}
