import type { Metadata } from 'next';
import { EmptyState, StoryCard } from '@glacier/ui';
import { t } from '@glacier/i18n';
import { fmtPeriod, tx } from '@articles/charts';
import { Cover } from '@/components/Cover';
import { HomeFeed } from '@/components/HomeFeed';
import { SearchBox } from '@/components/SearchBox';
import { ARTICLES, editionOf, getPipeline, topicTree } from '@/lib/content';
import { langOf } from '@/lib/page';
import { countForms, s } from '@/lib/strings';
import { plainText as strip } from '@/lib/text';

export const metadata: Metadata = { alternates: { languages: { en: '/en', ko: '/ko', 'x-default': '/' } } };

/** Latest: every article, newest first, with the search field and the topic filter in the rail. */
export default async function Home({ params }: { params: Promise<{ lang: string }> }) {
  const lang = await langOf(params);
  const base = `/${lang}`;
  const items = ARTICLES.map((a) => {
    const { ed } = editionOf(a, lang);
    const rt = a.meta.readTime?.[lang];
    const type = getPipeline(a.meta.type);
    return {
      slug: a.slug,
      topics: a.meta.topics.map((x) => x.id),
      card: (
        <StoryCard lang={lang} kicker={[type ? tx(type.name, lang) : null, ed.kicker].filter(Boolean).join(' · ')} title={ed.title} dek={strip(ed.dek)} href={`${base}/a/${a.slug}`}
          date={fmtPeriod(a.meta.date, lang, 'auto')} readTime={rt ? t(lang, 'readTime', { n: rt }) : undefined}
          isNew={!a.meta.review?.approved ? false : undefined} thumbnail={a.cover ? <Cover article={a} lang={lang} /> : undefined} />
      ),
    };
  });
  const groups = topicTree(lang).map((g) => ({ id: g.id, label: g.label, topics: g.topics.map((x) => ({ id: x.id, label: tx(x.label, lang), n: x.articles.length })) }));
  return (
    <div className="shell">
      <h1 className="gl-visually-hidden">{s(lang, 'nav.latest')}</h1>
      {ARTICLES.length ? (
        <HomeFeed base={base} items={items} groups={groups} topicsHref={`${base}/topics`} railLabel={s(lang, 'home.rail')}
          search={<SearchBox lang={lang} id="search-rail" />} searchShort={<SearchBox lang={lang} id="search-row" short />}
          labels={{
            all: s(lang, 'feed.all'), allTopics: s(lang, 'feed.allTopics'), topics: s(lang, 'nav.topics'), topic: s(lang, 'feed.topic'),
            clear: s(lang, 'feed.clear'), pages: s(lang, 'feed.pages'), page: s(lang, 'feed.page'), prev: s(lang, 'feed.prev'),
            next: s(lang, 'feed.next'), range: s(lang, 'feed.range'), count: countForms(lang, 'articles'),
          }} />
      ) : (
        <div className="home"><div className="home__feed"><EmptyState lang={lang} title={s(lang, 'home.empty')} body={s(lang, 'home.emptyBody')} /></div></div>
      )}
    </div>
  );
}
