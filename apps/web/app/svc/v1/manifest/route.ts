// GET /svc/v1/manifest: the articles app's views for the datasteg API (api.yaml).
import { BUILT, RELEASE } from '@/lib/svc-articles';
import { svcGuard, svcJson } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  const denied = svcGuard(req); if (denied) return denied;
  return svcJson({
    app: 'articles', surface: '1.0', release: RELEASE, built: BUILT,
    views: ['articles', 'article', 'facts', 'chart', 'glossary', 'topics'],
    hooks: ['search', 'item', 'economy'], item_kinds: ['article', 'term'],
  });
}
