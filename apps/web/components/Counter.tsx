'use client';
import { useEffect } from 'react';
import { usePathname } from 'next/navigation';

/** Counting with count.js (lib/count.ts loads it in the layout). */
type GoatCounter = { count?: (vars: { path: string; title?: string; event?: boolean }) => void };
const gc = () => (window as unknown as { goatcounter?: GoatCounter }).goatcounter;

/** Runs f once count.js has loaded. */
function whenReady(f: (count: NonNullable<GoatCounter['count']>) => void) {
  const count = gc()?.count;
  if (count) return f(count);
  document.querySelector('script[data-goatcounter]')?.addEventListener('load', () => { const c = gc()?.count; if (c) f(c); }, { once: true });
}

/** Download events, in the names the admin site reads (admin/apps/web/lib/goatcounter.ts byArticle):
 *  /pdf/<slug>-<lang>.pdf -> pdf:<slug>-<lang>, /data/<slug>/<file>.csv -> csv:<slug>/<file>. */
function eventName(a: HTMLAnchorElement): string | null {
  if (a.origin !== window.location.origin) return null;
  const pdf = a.pathname.match(/^\/pdf\/([a-z0-9-]+)\.pdf$/);
  if (pdf) return `pdf:${pdf[1]}`;
  const csv = a.pathname.match(/^\/data\/([a-z0-9-]+\/[A-Za-z0-9._-]+)\.csv$/);
  return csv ? `csv:${csv[1]}` : null;
}

/** One page view per path (the query string stays out, so /en/a/<slug>?utm_source=x counts as the article;
 *  count.js still sends the query separately for campaigns), and one event per PDF or CSV download. */
export function Counter() {
  const pathname = usePathname();
  useEffect(() => {
    if (pathname) whenReady((count) => count({ path: pathname }));
  }, [pathname]);
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const a = (e.target as Element | null)?.closest?.('a[href]');
      if (!(a instanceof HTMLAnchorElement)) return;
      const name = eventName(a);
      if (name) whenReady((count) => count({ path: name, title: a.pathname.split('/').pop(), event: true }));
    };
    document.addEventListener('click', onClick);
    document.addEventListener('auxclick', onClick);
    return () => { document.removeEventListener('click', onClick); document.removeEventListener('auxclick', onClick); };
  }, []);
  return null;
}
