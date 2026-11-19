import type { Metadata } from 'next';
import { tx } from '@articles/charts';
import { GlossaryFilter } from '@/components/GlossaryFilter';
import { ARTICLES, GLOSSARY, TOPICS, editionOf, getArticle } from '@/lib/content';
import { byInitial } from '@/lib/glossary';
import { langOf } from '@/lib/page';
import { s } from '@/lib/strings';

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const lang = await langOf(params);
  return { title: s(lang, 'glossaryTitle') };
}

/** Every term, in letter groups (A–Z; ㄱ–ㅎ in Korean). Each row carries its topics and articles as data
 *  attributes for the filter bar, and links to the term's page and the articles that use it. */
export default async function Glossary({ params }: { params: Promise<{ lang: string }> }) {
  const lang = await langOf(params);
  const other = lang === 'ko' ? 'en' : 'ko';
  const groups = byInitial(Object.values(GLOSSARY), lang);
  const topicLabel = new Map(TOPICS.map((x) => [x.id, tx(x.label, lang)]));
  const titleOf = (slug: string) => { const a = getArticle(slug); return a ? editionOf(a, lang).ed.title : slug; };
  return (
    <>
      <header className="page-head">
        <p className="gl-kicker"><a className="page-head__up" href={`/${lang}/about`}>{s(lang, 'nav.about')}</a></p>
        <h1>{s(lang, 'glossaryTitle')}</h1>
        <p className="dek">{s(lang, 'glossaryDek')}</p>
      </header>
      <div className="glx">
        <GlossaryFilter
          topics={TOPICS.filter((x) => x.terms.length).map((x) => ({ id: x.id, label: tx(x.label, lang) }))}
          articles={ARTICLES.filter((a) => a.terms.length).map((a) => ({ id: a.slug, label: editionOf(a, lang).ed.title }))}
          labels={{ topic: s(lang, 'gl.topic'), all: s(lang, 'gl.all'), inArticle: s(lang, 'gl.inArticle'), allArticles: s(lang, 'gl.allArticles'), showing: s(lang, 'gl.showing'), none: s(lang, 'gl.none'), clear: s(lang, 'gl.clear') }}
        />
        <nav className="glx-letters" aria-label={s(lang, 'glossaryTitle')}>
          {groups.map((g) => <a key={g.letter} href={`#letter-${g.letter}`}>{g.letter}</a>)}
        </nav>
        {groups.map((g) => (
          <section key={g.letter} className="glx-group" data-term-group aria-labelledby={`letter-${g.letter}`}>
            <h2 id={`letter-${g.letter}`} className="glx-group__letter">{g.letter}</h2>
            <dl>
              {g.terms.map((x) => {
                const alt = typeof x.term === 'string' ? null : x.term[other];
                return (
                  <div key={x.id} id={`term-${x.id}`} className="glx-row" data-term-row data-topics={x.topicIds.join(' ')} data-articles={x.articles.join(' ')}>
                    <dt>
                      <a href={`/${lang}/glossary/${x.id}`}>{tx(x.term, lang)}</a>
                      {alt && alt !== tx(x.term, lang) ? <span lang={other} className="glx-row__alt">{alt}</span> : null}
                    </dt>
                    <dd>
                      <p className="glx-row__def">{tx(x.definition, lang)}</p>
                      {x.articles.length || x.topicIds.length ? (
                        <p className="glx-row__meta">
                          {x.topicIds.map((id) => <a key={id} className="glx-row__topic" href={`/${lang}/glossary?topic=${id}`}>{topicLabel.get(id) ?? id}</a>)}
                          {x.articles.length ? (
                            <span className="glx-row__used">{s(lang, 'gl.usedIn')}: {x.articles.map((slug, i) => <span key={slug}>{i ? ' · ' : ''}<a href={`/${lang}/a/${slug}#terms`}>{titleOf(slug)}</a></span>)}</span>
                          ) : null}
                        </p>
                      ) : null}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </section>
        ))}
      </div>
    </>
  );
}
