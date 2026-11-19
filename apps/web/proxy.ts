import { NextResponse, type NextRequest } from 'next/server';

const LANGS = ['en', 'ko'];
const COOKIE = 'glacier-lang';

/** Korean if the browser lists Korean at all, whatever its rank ("en-US,en;q=0.9,ko;q=0.8" -> ko); otherwise English. */
function fromAcceptLanguage(header: string): string {
  const listed = header.split(',').map((part) => {
    const [tag, ...params] = part.trim().toLowerCase().split(';');
    const q = Number(params.find((p) => p.trim().startsWith('q='))?.split('=')[1] ?? 1);
    return { lang: tag.split('-')[0], q: Number.isFinite(q) ? q : 0 };
  }).filter((x) => x.q > 0).map((x) => x.lang);
  return listed.includes('ko') ? 'ko' : 'en';
}

/** Every page lives under /en/ or /ko/. A path without one is redirected: the reader's saved
 *  choice (cookie) first, then Korean for a browser that lists Korean, then English. */
export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const first = pathname.split('/')[1];
  if (LANGS.includes(first)) return NextResponse.next();
  const saved = req.cookies.get(COOKIE)?.value;
  const accept = req.headers.get('accept-language') ?? '';
  const lang = saved && LANGS.includes(saved) ? saved : fromAcceptLanguage(accept);
  const url = req.nextUrl.clone();
  url.pathname = `/${lang}${pathname === '/' ? '' : pathname}`;
  url.search = search;
  return NextResponse.redirect(url, 307);
}

export const config = {
  // Not for the health check, APIs, the internal views for the datasteg API (/svc/v1/…),
  // Next's own files, the PDF edition's print pages (/print/<lang>/<slug>, which carry their language), or files with
  // an extension (robots.txt, icons, PDFs).
  matcher: ['/((?!health|api/|svc/|_next/|print/|.*\\.[a-zA-Z0-9]+$).*)'],
};
