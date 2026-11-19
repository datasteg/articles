import { Fragment, type ReactNode, type MouseEventHandler } from 'react';
import { t, type Lang } from '@glacier/i18n';
import { cx, Icon } from './util';

export interface MastheadLink { label: string; href?: string; active?: boolean }

export function Masthead(p: { lang: Lang; name?: string; mark?: ReactNode; href?: string; links?: MastheadLink[]; actions?: ReactNode; className?: string }) {
  const links = p.links ?? [];
  return (
    <header className={cx('gl-mast', p.className)}>
      <a className="gl-wordmark" href={p.href ?? '/'}>{p.mark}{p.name ?? 'Glacier'}</a>
      {links.length ? (
        <nav className="gl-mast__nav" aria-label={t(p.lang, 'primaryNav')}>
          {links.map((l, i) => <a key={i} href={l.href ?? '#'} aria-current={l.active ? 'page' : undefined}>{l.label}</a>)}
        </nav>
      ) : null}
      <div className="gl-mast__actions">{p.actions}</div>
    </header>
  );
}

export interface LanguageOption { code: Lang; label: string; href?: string; onClick?: MouseEventHandler }

export function LanguageSwitch(p: { lang: Lang; current?: Lang; options?: LanguageOption[]; showIcon?: boolean; className?: string }) {
  const opts = p.options ?? [{ code: 'en', label: 'EN', href: '#' }, { code: 'ko', label: '한국어', href: '#' }];
  const cur = p.current ?? p.lang;
  return (
    <nav className={cx('gl-lang', p.className)} aria-label={t(p.lang, 'language')}>
      {p.showIcon !== false ? <span className="gl-lang__icon"><Icon name="globe" /></span> : null}
      {opts.map((o, i) => (
        <Fragment key={o.code}>
          {i > 0 ? <span className="gl-lang__sep" aria-hidden>/</span> : null}
          <a href={o.href ?? '#'} lang={o.code} hrefLang={o.code} aria-current={o.code === cur ? 'true' : undefined} onClick={o.onClick}>{o.label}</a>
        </Fragment>
      ))}
    </nav>
  );
}

export function Footer(p: { lang: Lang; name?: string; href?: string; links?: MastheadLink[]; note?: ReactNode; languageSwitch?: ReactNode; className?: string }) {
  const links = p.links ?? [];
  return (
    <footer className={cx('gl-foot', p.className)}>
      <div className="gl-foot__row">
        <a className="gl-wordmark gl-wordmark--sm" href={p.href ?? '/'}>{p.name ?? 'Glacier'}</a>
        {p.languageSwitch ?? null}
      </div>
      {links.length ? (
        <nav className="gl-foot__nav" aria-label={t(p.lang, 'footerNav')}>
          {links.map((l, i) => <a key={i} href={l.href ?? '#'}>{l.label}</a>)}
        </nav>
      ) : null}
      {p.note ? <p className="gl-foot__note">{p.note}</p> : null}
    </footer>
  );
}
