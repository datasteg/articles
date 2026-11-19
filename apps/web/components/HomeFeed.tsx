'use client';
import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from 'react';

export interface FeedItem { slug: string; topics: string[]; card: ReactNode }
export interface FeedGroup { id: string; label: string; topics: Array<{ id: string; label: string; n: number }> }

const PAGE_SIZE = 10;

/** The home page's feed and rail: the story cards, a topic filter that works in place (?topic=…, pushed to history so
 *  Back undoes it), a pager under the feed (?page=…), and on narrow screens one row with the search field and a
 *  "Topics" button instead of the rail. The cards are rendered on the server; without JavaScript every card shows
 *  and the topic links load the same page. */
export function HomeFeed(p: {
  base: string; items: FeedItem[]; groups: FeedGroup[]; topicsHref: string;
  search: ReactNode; searchShort: ReactNode; railLabel: string;
  labels: { all: string; allTopics: string; topics: string; topic: string; clear: string; pages: string; page: string; prev: string; next: string; range: string; count: string[] };
}) {
  const [ready, setReady] = useState(false);
  const [topic, setTopic] = useState('');
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const feed = useRef<HTMLDivElement>(null);
  const known = useMemo(() => new Map(p.groups.flatMap((g) => g.topics.map((x) => [x.id, x.label] as const))), [p.groups]);

  const fromUrl = useCallback(() => {
    const q = new URLSearchParams(window.location.search);
    const t = q.get('topic') ?? '';
    setTopic(known.has(t) ? t : '');
    setPage(Math.max(1, Number.parseInt(q.get('page') ?? '1', 10) || 1));
  }, [known]);
  useEffect(() => {
    fromUrl();
    setReady(true);
    window.addEventListener('popstate', fromUrl);
    return () => window.removeEventListener('popstate', fromUrl);
  }, [fromUrl]);

  const href = (t: string, n: number) => {
    const q = new URLSearchParams();
    if (t) q.set('topic', t);
    if (n > 1) q.set('page', String(n));
    const qs = q.toString();
    return qs ? `${p.base}?${qs}` : p.base;
  };
  const go = (t: string, n: number) => (e: MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;   // a new tab gets the URL
    e.preventDefault();
    setTopic(t);
    setPage(n);
    setOpen(false);
    window.history.pushState(null, '', href(t, n));
    if ((feed.current?.getBoundingClientRect().top ?? 0) < 0) feed.current?.scrollIntoView({ block: 'start' });
  };

  const list = ready ? p.items.filter((x) => !topic || x.topics.includes(topic)) : p.items;
  const pages = ready ? Math.max(1, Math.ceil(list.length / PAGE_SIZE)) : 1;
  const cur = Math.min(page, pages);
  const shown = ready ? list.slice((cur - 1) * PAGE_SIZE, cur * PAGE_SIZE) : list;
  const n = (k: number) => p.labels.count[k === 1 ? 0 : 1].replace('{n}', String(k));

  const topicList = (
    <ul className="feed-topics">
      <li><a href={href('', 1)} aria-current={ready && !topic ? 'true' : undefined} onClick={go('', 1)}>
        <span>{p.labels.all}</span><span className="feed-topics__n">{p.items.length}</span></a></li>
      {p.groups.map((g) => (
        <li key={g.id}>
          <p className="feed-topics__group">{g.label}</p>
          <ul>
            {g.topics.map((x) => (
              <li key={x.id}><a href={href(x.id, 1)} aria-current={topic === x.id ? 'true' : undefined} onClick={go(topic === x.id ? '' : x.id, 1)}>
                <span>{x.label}</span><span className="feed-topics__n">{x.n}</span></a></li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );

  return (
    <div className="home">
      <div className="home__feed" ref={feed}>
        <div className="feed-tools">
          <div className="feed-tools__row">
            {p.searchShort}
            <button type="button" className="feed-tools__topics" aria-expanded={open} aria-controls="feed-topics-sheet" onClick={() => setOpen((x) => !x)}>
              {p.labels.topics}
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="m6 9 6 6 6-6" /></svg>
            </button>
          </div>
          <div id="feed-topics-sheet" className="feed-tools__sheet" hidden={!open}>
            {topicList}
            <a className="feed-topics__more gl-link" href={p.topicsHref}>{p.labels.allTopics} →</a>
          </div>
        </div>
        <div className="feed-status" aria-live="polite">
          {topic ? (
            <p>
              <span>{p.labels.topic}: <b>{known.get(topic)}</b> · {n(list.length)}</span>
              <a className="feed-status__clear" href={href('', 1)} onClick={go('', 1)}><span aria-hidden>✕ </span>{p.labels.clear}</a>
            </p>
          ) : null}
        </div>
        <div className="feed-list">
          {shown.map((x) => <div key={x.slug} className="feed-item">{x.card}</div>)}
        </div>
        {pages > 1 ? (
          <nav className="pager" aria-label={p.labels.pages}>
            <div className="pager__row">
              {cur > 1
                ? <a className="pager__btn" rel="prev" href={href(topic, cur - 1)} onClick={go(topic, cur - 1)}>‹ {p.labels.prev}</a>
                : <span className="pager__btn" aria-disabled="true">‹ {p.labels.prev}</span>}
              {pageList(cur, pages).map((x, i) => (x === 0
                ? <span key={`gap${i}`} className="pager__gap" aria-hidden>…</span>
                : <a key={x} className="pager__btn" href={href(topic, x)} aria-current={x === cur ? 'page' : undefined}
                  aria-label={p.labels.page.replace('{n}', String(x))} onClick={go(topic, x)}>{x}</a>))}
              {cur < pages
                ? <a className="pager__btn" rel="next" href={href(topic, cur + 1)} onClick={go(topic, cur + 1)}>{p.labels.next} ›</a>
                : <span className="pager__btn" aria-disabled="true">{p.labels.next} ›</span>}
            </div>
            <p className="pager__count">{p.labels.range.replace('{from}', String((cur - 1) * PAGE_SIZE + 1)).replace('{to}', String((cur - 1) * PAGE_SIZE + shown.length)).replace('{n}', String(list.length))}</p>
          </nav>
        ) : null}
      </div>
      <aside className="home__rail" aria-label={p.railLabel}>
        <div className="rail-block">{p.search}</div>
        <nav className="rail-block" aria-label={p.labels.topics}>
          <p className="gl-kicker gl-kicker--muted">{p.labels.topics}</p>
          {topicList}
          <a className="feed-topics__more gl-link" href={p.topicsHref}>{p.labels.allTopics} →</a>
        </nav>
      </aside>
    </div>
  );
}

/** Page numbers with gaps (0): all of them up to 7 pages, else the first, the last and the ones around the current. */
function pageList(cur: number, total: number): number[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const keep = [...new Set([1, total, cur - 1, cur, cur + 1])].filter((x) => x >= 1 && x <= total).sort((a, b) => a - b);
  const out: number[] = [];
  for (const x of keep) {
    if (out.length && x - out[out.length - 1] > 1) out.push(0);
    out.push(x);
  }
  return out;
}
