// GET /svc/v1/articles/{slug}?lang=&section=: one article for reading, as its page shows it in the asked edition
// (whole articles, with the terms and the citation in every answer). Sections are Markdown with citations as
// source ids ([S3]) and charts referenced by id; `sources` is the article's sources.json, quotes as published.
import { getArticle } from '@/lib/content';
import { SLUG, articleData, articleSummary, envelope, pageOf, reuseNote, sourceOut } from '@/lib/svc-articles';
import { svcError, svcGuard, svcJson, svcLang } from '@/lib/svc';

export const dynamic = 'force-dynamic';

export async function GET(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const denied = svcGuard(req); if (denied) return denied;
  const { slug } = await params;
  const url = new URL(req.url);
  const lang = svcLang(url);
  const a = SLUG.test(slug) ? getArticle(slug) : undefined;
  if (!a) return svcError(404, 'unknown-article', 'Unknown article', `${slug.slice(0, 100)} is not the slug of a published datasteg article. The articles view lists them (slugs such as won-after-rate-hold).`);
  const section = url.searchParams.get('section') || '';
  const data = articleData(a, lang, section || undefined);
  if (section && !data.sections.length) return svcError(400, 'bad-parameter', 'Unknown section', `section must be one of this article's section ids: ${(data.section_ids ?? []).join(', ')}; leave it out for the whole article.`);
  return svcJson(envelope('article', lang, {
    page: pageOf(a, lang) + (section ? `#sec-${section}` : ''),
    summary: articleSummary(a),
    data,
    sources: a.sources.map((x) => sourceOut(x, data.edition)),
    notes: [
      reuseNote(lang),
      'Citations in the text are source ids ([S3]); sources lists them as the article\'s references, with each archive document\'s quote as the article published it.',
      'Charts are referenced by id: each chart\'s data, as table rows and as the CSV the page offers, and its metadata come from the article\'s facts view with chart=<id> (the article_numbers tool) or its charts view.',
      ...(data.fallback ? [`This article has no ${lang === 'ko' ? 'Korean' : 'English'} edition yet; the ${data.edition === 'ko' ? 'Korean' : 'English'} edition is shown, as on the page.`] : []),
    ],
  }));
}
