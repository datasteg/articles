import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { Tag } from '@glacier/ui';
import { LANGS } from '@glacier/i18n';
import { tx } from '@articles/charts';
import { GLOSSARY, TOPICS, editionOf, getArticle } from '@/lib/content';
import { langOf } from '@/lib/page';
import { s } from '@/lib/strings';

type Params = Promise<{ lang: string; id: string }>;
export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.flatMap((lang) => Object.keys(GLOSSARY).map((id) => ({ lang, id })));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const lang = await langOf(params);
  const g = GLOSSARY[id];
  return g ? { title: `${tx(g.term, lang)} — ${s(lang, 'glossaryTitle')}`, description: tx(g.definition, lang) } : {};
}

/** One term: its general definition, then each article that uses it with how that article uses it. */
export default async function Term({ params }: { params: Params }) {
  const { id } = await params;
  const lang = await langOf(params);
  const g = GLOSSARY[id];
  if (!g) notFound();
  const other = lang === 'ko' ? 'en' : 'ko';
  const alt = typeof g.term === 'string' ? null : g.term[other];
  const topicLabel = new Map(TOPICS.map((x) => [x.id, tx(x.label, lang)]));
  const see = (g.see ?? []).map((k) => GLOSSARY[k]).filter(Boolean);
  return (
    <>
      <header className="page-head">
        <p className="gl-kicker"><a className="page-head__up" href={`/${lang}/glossary`}>{s(lang, 'glossaryTitle')}</a></p>
        <h1>{tx(g.term, lang)}{alt && alt !== tx(g.term, lang) ? <span lang={other} className="term-alt">{alt}</span> : null}</h1>
        <p className="dek">{tx(g.definition, lang)}</p>
      </header>
      <section className="term-block" aria-labelledby="in-h">
        <h2 id="in-h" className="block-h">{s(lang, 'gl.inArticles')}</h2>
        {g.articles.length ? (
          <ul className="term-uses">
            {g.articles.map((slug) => {
              const a = getArticle(slug);
              if (!a) return null;
              const ctx = a.terms.find((x) => x.id === id)?.context;
              return (
                <li key={slug}>
                  <a className="term-uses__title" href={`/${lang}/a/${slug}#terms`}>{editionOf(a, lang).ed.title}</a>
                  {ctx ? <p className="term-uses__ctx">{tx(ctx, lang)}</p> : null}
                </li>
              );
            })}
          </ul>
        ) : <p className="term-block__none">{s(lang, 'gl.notUsed')}</p>}
      </section>
      {see.length ? (
        <section className="term-block" aria-labelledby="see-h">
          <h2 id="see-h" className="block-h">{s(lang, 'gl.related')}</h2>
          <div className="gl-tags">{see.map((x) => <Tag key={x.id} href={`/${lang}/glossary/${x.id}`}>{tx(x.term, lang)}</Tag>)}</div>
        </section>
      ) : null}
      {g.topicIds.length ? (
        <section className="term-block" aria-labelledby="tp-h">
          <h2 id="tp-h" className="block-h">{s(lang, 'nav.topics')}</h2>
          <div className="gl-tags">{g.topicIds.map((t) => <Tag key={t} href={`/${lang}/glossary?topic=${t}`}>{topicLabel.get(t) ?? t}</Tag>)}</div>
        </section>
      ) : null}
    </>
  );
}
