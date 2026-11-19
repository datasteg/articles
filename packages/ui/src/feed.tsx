import { Fragment, type ReactNode } from 'react';
import { t, type Lang } from '@glacier/i18n';
import { Button } from './actions';
import { cx, initials, pad2, Icon, StrataArt } from './util';

export function Tag(p: { kind?: 'topic' | 'jel' | 'new'; href?: string; children?: ReactNode; className?: string }) {
  const kind = p.kind ?? 'topic';
  const cls = cx('gl-tag', kind !== 'topic' && 'gl-tag--' + kind, p.className);
  return p.href ? <a className={cls} href={p.href}>{p.children}</a> : <span className={cls}>{p.children}</span>;
}

export interface StoryCardProps {
  lang: Lang; kicker?: string;
  /** The finding as a sentence — not the paper's title. */
  title: string; dek?: string; href?: string;
  date?: string; readTime?: string; tags?: string[];
  thumbnail?: string | ReactNode; thumbnailAlt?: string; isNew?: boolean; className?: string;
}
export function StoryCard(p: StoryCardProps) {
  const when = [p.date, p.readTime].filter(Boolean).join(' · ');
  const meta: ReactNode[] = [];
  if (p.isNew) meta.push(<Tag key="n" kind="new">{t(p.lang, 'new')}</Tag>);
  if (when) meta.push(<span key="w">{when}</span>);
  (p.tags ?? []).forEach((tg, i) => meta.push(<Tag key={'t' + i} kind="jel">{tg}</Tag>));
  return (
    <article className={cx('gl-story', p.className)} lang={p.lang}>
      <div className="gl-story__body">
        {p.kicker ? <p className="gl-story__kicker">{p.kicker}</p> : null}
        <a className="gl-story__link" href={p.href ?? '#'}>
          <h3 className="gl-story__title">{p.title}</h3>
          {p.dek ? <p className="gl-story__dek">{p.dek}</p> : null}
        </a>
        {meta.length ? <div className="gl-story__meta">{meta}</div> : null}
      </div>
      {p.thumbnail ? (
        <div className="gl-story__thumb">
          {typeof p.thumbnail === 'string' ? <img src={p.thumbnail} alt={p.thumbnailAlt ?? ''} loading="lazy" /> : p.thumbnail}
        </div>
      ) : null}
    </article>
  );
}

export function IssueHero(p: { lang: Lang; issue: string; date?: string; title: string; note?: string; meta?: string; children?: ReactNode; className?: string; id?: string }) {
  const id = p.id ?? 'issue-hero';
  const kicker = [t(p.lang, 'issue', { n: p.lang === 'ko' ? Number(p.issue) : p.issue }), p.date].filter(Boolean).join(' · ');
  return (
    <section className={cx('gl-hero', p.className)} aria-labelledby={id} lang={p.lang}>
      <StrataArt />
      <div className="gl-hero__inner">
        <p className="gl-hero__kicker">{kicker}</p>
        <h1 className="gl-hero__title" id={id}>{p.title}</h1>
        {p.note ? <p className="gl-hero__note">{p.note}</p> : null}
        {p.meta ? <p className="gl-hero__meta">{p.meta}</p> : null}
        {p.children}
      </div>
    </section>
  );
}

export function ArticleHeader(p: {
  lang: Lang; kicker?: string; title: string; subtitle?: string; author: string; authorInitials?: string;
  role?: string; readTime?: string; date?: string; leading?: ReactNode; actions?: ReactNode | null; className?: string;
}) {
  const meta = [p.role, p.readTime, p.date].filter(Boolean).join(' · ');
  const actions = p.actions !== undefined ? p.actions : (
    <>
      <Button variant="quiet" icon="bookmark" aria-label={t(p.lang, 'save')} />
      <Button variant="quiet" icon="share" aria-label={t(p.lang, 'share')} />
    </>
  );
  return (
    <header className={cx('gl-ahead', p.className)} lang={p.lang}>
      {p.kicker ? <p className="gl-kicker">{p.kicker}</p> : null}
      <h1 className="gl-ahead__title">{p.title}</h1>
      {p.subtitle ? <p className="gl-ahead__dek">{p.subtitle}</p> : null}
      <div className="gl-byline">
        <span className="gl-avatar" aria-hidden>{p.authorInitials ?? initials(p.author)}</span>
        <div>
          <p className="gl-byline__name">{p.author}</p>
          {meta ? <p className="gl-byline__meta">{meta}</p> : null}
        </div>
      </div>
      <div className="gl-actionbar">
        <div className="gl-actionbar__group">{p.leading ?? null}</div>
        <div className="gl-actionbar__group">{actions}</div>
      </div>
    </header>
  );
}

export interface PaperFact { label: string; value: ReactNode }
export function PaperCard(p: {
  lang: Lang; label?: string; title: string; titleTranslated?: string; paperLang?: string;
  authors?: string; journal?: string; citation?: string; year?: string | number;
  doi?: string; href?: string; jel?: string[]; openAccess?: boolean; facts?: PaperFact[]; className?: string;
}) {
  const facts = p.facts ?? [];
  const venue = [p.citation, p.year].filter(Boolean).join(', ');
  const pl = p.paperLang ?? 'en';
  const label = p.label ?? t(p.lang, 'paper');
  return (
    <aside className={cx('gl-paper', p.className)} aria-label={label} lang={p.lang}>
      <div className="gl-paper__head">
        <p className="gl-kicker gl-kicker--muted">{label}</p>
        {p.openAccess ? <span className="gl-chip-oa"><Icon name="unlock" />{t(p.lang, 'openAccess')}</span> : null}
      </div>
      <p className="gl-paper__title" lang={pl}>{p.title}</p>
      {p.titleTranslated ? <p className="gl-paper__title-tr">{p.titleTranslated}</p> : null}
      {p.authors ? <p className="gl-paper__authors" lang={pl}>{p.authors}</p> : null}
      {p.journal ? <p className="gl-paper__venue" lang={pl}><em>{p.journal}</em>{venue ? ', ' + venue : null}</p> : null}
      {facts.length ? (
        <dl className="gl-paper__facts">
          {facts.map((f, i) => <Fragment key={i}><dt>{f.label}</dt><dd>{f.value}</dd></Fragment>)}
        </dl>
      ) : null}
      {p.doi || p.jel?.length ? (
        <div className="gl-paper__foot">
          {p.doi ? <a className="gl-doi" href={p.href ?? 'https://doi.org/' + p.doi} lang="en">{'doi:' + p.doi}</a> : null}
          {p.jel?.length ? <span className="gl-tags">{p.jel.map((j, i) => <Tag key={i} kind="jel">{j}</Tag>)}</span> : null}
        </div>
      ) : null}
    </aside>
  );
}

export function KeyFindings(p: { lang: Lang; title?: string; items: ReactNode[]; className?: string }) {
  const title = p.title ?? t(p.lang, 'findings');
  return (
    <section className={cx('gl-findings', p.className)} aria-label={title} lang={p.lang}>
      <h2 className="gl-findings__title">{title}</h2>
      <ol className="gl-findings__list">
        {p.items.map((it, i) => (
          <li key={i} className="gl-findings__item">
            <span className="gl-findings__num" aria-hidden>{pad2(i + 1)}</span>
            <span className="gl-findings__text">{it}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function StrataRule(p: { className?: string } = {}) {
  return <div className={cx('gl-strata', p.className)} role="separator"><span /><span /><span /></div>;
}

export function Insight(p: { lang: Lang; label?: string; children: ReactNode; by?: string; className?: string }) {
  const label = p.label ?? t(p.lang, 'ourRead');
  const body = typeof p.children === 'string' ? <p>{p.children}</p> : p.children;
  return (
    <aside className={cx('gl-insight', p.className)} aria-label={label} lang={p.lang}>
      <StrataRule />
      <p className="gl-insight__label">{label}</p>
      <div className="gl-insight__body">{body}</div>
      {p.by ? <p className="gl-insight__by">{'— ' + p.by}</p> : null}
    </aside>
  );
}

export function Figure(p: { lang: Lang; src?: string; alt?: string; children?: ReactNode; caption?: ReactNode; source?: string; width?: 'column' | 'wide' | 'full'; className?: string }) {
  const width = p.width ?? 'column';
  const media = p.src
    ? <img className="gl-figure__media" src={p.src} alt={p.alt ?? ''} loading="lazy" />
    : <div className="gl-figure__media" role={p.alt ? 'img' : undefined} aria-label={p.alt || undefined}>{p.children}</div>;
  return (
    <figure className={cx('gl-figure', 'gl-figure--' + width, p.className)} lang={p.lang}>
      {media}
      {p.caption || p.source ? (
        <figcaption>
          {p.caption ?? null}
          {p.source ? <span className="gl-figure__source">{t(p.lang, 'source') + p.source}</span> : null}
        </figcaption>
      ) : null}
    </figure>
  );
}

export function Notice(p: { lang: Lang; tone?: 'info' | 'good' | 'warning' | 'critical'; title?: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  const tone = p.tone ?? 'info';
  return (
    <div className={cx('gl-notice', 'gl-notice--' + tone, p.className)} role={tone === 'critical' ? 'alert' : 'status'} lang={p.lang}>
      <span className="gl-notice__icon"><Icon name={tone} /></span>
      <div>
        {p.title ? <p className="gl-notice__title">{p.title}</p> : null}
        {p.children ? <div className="gl-notice__body">{p.children}</div> : null}
        {p.action ?? null}
      </div>
    </div>
  );
}

export function EmptyState(p: { lang: Lang; title?: string; body?: string; action?: ReactNode; className?: string }) {
  return (
    <div className={cx('gl-empty', p.className)} lang={p.lang}>
      <div className="gl-empty__mark" aria-hidden><span /><span /><span /></div>
      <p className="gl-empty__title">{p.title ?? t(p.lang, 'empty')}</p>
      {p.body ? <p className="gl-empty__body">{p.body}</p> : null}
      {p.action ?? null}
    </div>
  );
}

export function Skeleton(p: { lang: Lang; variant?: 'text' | 'tile' | 'chart'; lines?: number; height?: number }) {
  const v = p.variant ?? 'text';
  const label = t(p.lang, 'loading');
  if (v === 'chart') return <div className="gl-skel gl-skel--chart" style={{ height: (p.height ?? 320) + 'px' }} aria-label={label} role="status">{[0, 1, 2, 3].map((i) => <span key={i} />)}</div>;
  if (v === 'tile') return <div className="gl-skel gl-skel--tile" role="status" aria-label={label}><span /><span /><span /></div>;
  const n = p.lines ?? 3;
  return <div className="gl-skel gl-skel--text" role="status" aria-label={label}>{Array.from({ length: n }, (_, i) => <span key={i} style={{ width: i === n - 1 ? '60%' : '100%' }} />)}</div>;
}
