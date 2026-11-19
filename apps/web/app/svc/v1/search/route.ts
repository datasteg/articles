// GET /svc/v1/search?q=&lang=&limit=: articles (title, kicker, dek, findings, the glossary terms they use) and
// glossary terms, searched in both editions; titles and links in the asked language. score 0–1, an exact title, slug
// or term = 1.
import { clip, intParam, search } from '@/lib/svc-articles';
import { svcError, svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const denied = svcGuard(req); if (denied) return denied;
  const url = new URL(req.url);
  const lang = svcLang(url);
  const q = (url.searchParams.get('q') || '').trim();
  if (!q) return svcError(400, 'bad-parameter', 'Missing query', 'q is the text to search for, such as korea, won or spread.');
  if (q.length > 200) return svcError(400, 'bad-parameter', 'Query too long', `q is at most 200 characters; got ${q.length}.`);
  const limit = intParam(url, 'limit', 10, 1, 20);
  if (typeof limit === 'string') return svcError(400, 'bad-parameter', 'Bad limit', limit);
  return svcJson({ app: 'articles', query: clip(q, 200), items: search(q, lang, limit) });
}
