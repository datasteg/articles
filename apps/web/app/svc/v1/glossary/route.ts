// GET /svc/v1/glossary?topic=&article=&lang=: the glossary page's terms, in its dictionary order, each with its
// general definition, topics, related terms and the articles that use it.
import { ARTICLES, TOPICS } from '@/lib/content';
import { envelope, sortedTerms, termOut, type Table } from '@/lib/svc-articles';
import { svcError, svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const denied = svcGuard(req); if (denied) return denied;
  const url = new URL(req.url);
  const lang = svcLang(url);
  const topic = url.searchParams.get('topic') || '';
  const article = url.searchParams.get('article') || '';
  if (topic && !TOPICS.some((t) => t.id === topic)) return svcError(400, 'bad-parameter', 'Unknown topic', `topic must be one of: ${TOPICS.map((t) => t.id).join(', ')}.`);
  if (article && !ARTICLES.some((a) => a.slug === article)) return svcError(400, 'bad-parameter', 'Unknown article', `article is an article slug; The articles view lists them.`);
  const terms = sortedTerms(lang).filter((g) => (!topic || (g.topicIds ?? []).includes(topic)) && (!article || (g.articles ?? []).includes(article))).map((g) => termOut(g, lang));
  const table: Table = {
    columns: [{ id: 'id', label: 'Id' }, { id: 'term', label: 'Term' }, { id: 'definition', label: 'Definition' }, { id: 'topics', label: 'Topics' }, { id: 'articles', label: 'Articles' }, { id: 'page', label: 'Page' }],
    rows: terms.map((t) => [t.id, t.term, t.definition, t.topics.join(' '), t.articles.join(' '), t.page]),
  };
  const filters = [topic && `topic ${topic}`, article && `article ${article}`].filter(Boolean).join(', ');
  return svcJson(envelope('glossary', lang, {
    page: `/${lang}/glossary${topic ? `?topic=${topic}` : ''}`,
    summary: `The datasteg articles glossary${filters ? ` (${filters})` : ''}: ${terms.length} term${terms.length === 1 ? '' : 's'} in plain words, each with a general definition and the articles that use it.`,
    data: { count: terms.length, terms }, table,
  }));
}
