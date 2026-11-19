'use client';

import { useEffect, useRef, useState } from 'react';

export interface TocItem { id: string; label: string; summary?: string | null }

/** "Contents" at the top right of an article: where the reader is, how far through, and one line on each part.
 *  A pill that opens a card; on screens wide enough for a rail beside the wide figures, the card stays open. */
export function Toc({ items, title }: { items: TocItem[]; title: string }) {
  const [active, setActive] = useState(items[0]?.id);
  const [progress, setProgress] = useState(0);
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(false);
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const els = items.map((x) => document.getElementById(x.id)).filter((x): x is HTMLElement => Boolean(x));
    const onScroll = () => {
      const line = window.innerHeight * 0.3;   // the part whose top has passed 30% of the screen is the one being read
      let cur = els[0]?.id;
      for (const el of els) if (el.getBoundingClientRect().top <= line) cur = el.id;
      setActive(cur);
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0);
      setShown(window.scrollY > window.innerHeight * 0.4);   // the pill appears once the reader is past the title
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => { window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll); };
  }, [items]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onDown = (e: MouseEvent) => { if (root.current && !root.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => { document.removeEventListener('keydown', onKey); document.removeEventListener('mousedown', onDown); };
  }, [open]);

  const idx = Math.max(0, items.findIndex((x) => x.id === active));
  const r = 9, c = 2 * Math.PI * r;
  return (
    <nav ref={root} className="toc" aria-label={title} data-open={open || undefined} data-shown={shown || open || undefined}>
      <button type="button" className="toc__pill" aria-expanded={open} aria-controls="toc-card" onClick={() => setOpen((o) => !o)}>
        <svg className="toc__ring" viewBox="0 0 24 24" width="24" height="24" aria-hidden>
          <circle cx="12" cy="12" r={r} className="toc__ring-track" />
          <circle cx="12" cy="12" r={r} className="toc__ring-fill" strokeDasharray={c} strokeDashoffset={c * (1 - progress)} />
        </svg>
        <span className="toc__now">
          <span className="toc__kicker">{title} · {idx + 1}/{items.length}</span>
          <span className="toc__current">{items[idx]?.label}</span>
        </span>
        <svg className="toc__chev" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="m6 9 6 6 6-6" /></svg>
      </button>
      <div id="toc-card" className="toc__card">
        <p className="toc__h">{title}</p>
        <ol className="toc__list" style={{ ['--toc-p' as string]: progress }}>
          {items.map((x, i) => (
            <li key={x.id} className={x.id === active ? 'is-active' : i < idx ? 'is-read' : undefined}>
              <a href={`#${x.id}`} aria-current={x.id === active ? 'location' : undefined} onClick={() => setOpen(false)}>
                <span className="toc__n">{String(i + 1).padStart(2, '0')}</span>
                <span className="toc__t">{x.label}</span>
                {x.summary ? <span className="toc__s">{x.summary}</span> : null}
              </a>
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );
}
