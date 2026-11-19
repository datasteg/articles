'use client';
import { useEffect, useState } from 'react';

interface Option { id: string; label: string }

/** The glossary's filter bar: topic chips and an "In article" select. It shows and hides the server-rendered rows
 *  ([data-term-row] with data-topics and data-articles) and their letter groups, and keeps the choice in the URL
 *  (?topic=…&article=…) so topic pages and articles can link to a filtered glossary. Without JavaScript the bar is
 *  not shown and every term is listed. */
export function GlossaryFilter(p: {
  topics: Option[]; articles: Option[];
  labels: { topic: string; all: string; inArticle: string; allArticles: string; showing: string; none: string; clear: string };
}) {
  const [ready, setReady] = useState(false);
  const [topic, setTopic] = useState('');
  const [article, setArticle] = useState('');
  const [shown, setShown] = useState({ n: 0, total: 0 });

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    setTopic(p.topics.some((x) => x.id === q.get('topic')) ? (q.get('topic') as string) : '');
    setArticle(p.articles.some((x) => x.id === q.get('article')) ? (q.get('article') as string) : '');
    setReady(true);
  }, [p.topics, p.articles]);

  useEffect(() => {
    if (!ready) return;
    const rows = [...document.querySelectorAll<HTMLElement>('[data-term-row]')];
    let n = 0;
    for (const r of rows) {
      const ok = (!topic || (r.dataset.topics ?? '').split(' ').includes(topic)) && (!article || (r.dataset.articles ?? '').split(' ').includes(article));
      r.hidden = !ok;
      if (ok) n++;
    }
    for (const g of document.querySelectorAll<HTMLElement>('[data-term-group]')) g.hidden = !g.querySelector('[data-term-row]:not([hidden])');
    setShown({ n, total: rows.length });
    const q = new URLSearchParams(window.location.search);
    if (topic) q.set('topic', topic); else q.delete('topic');
    if (article) q.set('article', article); else q.delete('article');
    const qs = q.toString();
    window.history.replaceState(null, '', `${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash}`);
  }, [ready, topic, article]);

  if (!ready) return null;
  return (
    <div className="glx-filter" role="search">
      <div className="glx-filter__topics" role="group" aria-label={p.labels.topic}>
        {[{ id: '', label: p.labels.all }, ...p.topics].map((x) => (
          <button key={x.id || 'all'} type="button" className="glx-chip" aria-pressed={topic === x.id} onClick={() => setTopic(x.id)}>{x.label}</button>
        ))}
      </div>
      <label className="glx-filter__article">
        <span>{p.labels.inArticle}</span>
        <span className="gl-select">
          <select className="gl-input gl-select__el" value={article} onChange={(e) => setArticle(e.target.value)}>
            <option value="">{p.labels.allArticles}</option>
            {p.articles.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
          <span className="gl-select__chev" aria-hidden>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
          </span>
        </span>
      </label>
      <p className="glx-filter__count" aria-live="polite">
        {shown.n ? p.labels.showing.replace('{n}', String(shown.n)).replace('{total}', String(shown.total)) : p.labels.none}
        {topic || article ? <button type="button" className="glx-filter__clear" onClick={() => { setTopic(''); setArticle(''); }}>{p.labels.clear}</button> : null}
      </p>
    </div>
  );
}
