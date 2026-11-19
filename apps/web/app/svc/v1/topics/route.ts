// GET /svc/v1/topics?lang=: the topic registry (config/topics.yaml) as the Topics page groups it: each group, its
// topics, their articles (newest first) and how many glossary terms each has.
import { envelope, topicGroups, type Table } from '@/lib/svc-articles';
import { svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const denied = svcGuard(req); if (denied) return denied;
  const lang = svcLang(new URL(req.url));
  const groups = topicGroups(lang);
  const en = topicGroups('en');
  const n = groups.reduce((k, g) => k + g.topics.length, 0);
  const table: Table = {
    columns: [{ id: 'group', label: 'Group' }, { id: 'topic', label: 'Topic' }, { id: 'label', label: 'Label' }, { id: 'articles', label: 'Articles', unit: 'count' }, { id: 'terms', label: 'Terms', unit: 'count' }, { id: 'page', label: 'Page' }],
    rows: groups.flatMap((g) => g.topics.map((t) => [g.id, t.id, t.label, t.articles.length, t.terms, t.page])),
  };
  return svcJson(envelope('topics', lang, {
    page: `/${lang}/topics`,
    summary: `${n} datasteg article topics in ${groups.length} groups (${en.map((g) => g.label).join(', ')}), each with its articles and glossary terms.`,
    data: { groups }, table,
  }));
}
