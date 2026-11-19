import type { Metadata } from 'next';
import { tx } from '@articles/charts';
import { editionOf, getArticle, topicTree } from '@/lib/content';
import { langOf } from '@/lib/page';
import { count, s } from '@/lib/strings';

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const lang = await langOf(params);
  return { title: s(lang, 'nav.topics') };
}

/** Topics as a tree: the groups of config/topics.yaml, their topics that have articles, and those articles. A topic
 *  opens the home page filtered to it; its term count opens the glossary filtered to it. */
export default async function Topics({ params }: { params: Promise<{ lang: string }> }) {
  const lang = await langOf(params);
  return (
    <>
      <header className="page-head">
        <h1>{s(lang, 'nav.topics')}</h1>
        <p className="dek">{s(lang, 'topics.dek')}</p>
      </header>
      <div className="topic-tree">
        {topicTree(lang).map((g) => (
          <details key={g.id} className="topic-tree__group" open>
            <summary>
              <svg className="topic-tree__chev" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="m9 6 6 6-6 6" /></svg>
              <span className="topic-tree__group-name">{g.label}</span>
              <span className="topic-tree__n">{count(lang, 'articles', new Set(g.topics.flatMap((x) => x.articles)).size)}</span>
            </summary>
            <ul className="topic-tree__topics">
              {g.topics.map((x) => (
                <li key={x.id} className="topic-tree__topic">
                  <div className="topic-tree__row">
                    <a className="topic-tree__name" href={`/${lang}?topic=${x.id}`}>{tx(x.label, lang)}</a>
                    <span className="topic-tree__n">
                      {count(lang, 'articles', x.articles.length)}
                      {x.terms.length ? <> · <a href={`/${lang}/glossary?topic=${x.id}`}>{count(lang, 'terms', x.terms.length)}</a></> : null}
                    </span>
                  </div>
                  <ul className="topic-tree__articles">
                    {x.articles.map((slug) => {
                      const a = getArticle(slug);
                      return a ? <li key={slug}><a href={`/${lang}/a/${slug}`}>{editionOf(a, lang).ed.title}</a></li> : null;
                    })}
                  </ul>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </>
  );
}
