// GET /health: the container healthcheck (ds-deploy waits for 200 before routing traffic).
import data from '../../generated/content.json';

export const dynamic = 'force-dynamic';

export function GET() {
  return Response.json(
    { status: 'ok', service: 'articles', version: process.env.APP_VERSION ?? 'dev', built: process.env.BUILD_TIME,
      articles: (data as { articles: unknown[] }).articles.length, time: new Date().toISOString() },
    { headers: { 'cache-control': 'no-store' } },
  );
}
