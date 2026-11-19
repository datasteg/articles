'use client';
import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { Masthead } from '@glacier/ui';
import { t, type Lang } from '@glacier/i18n';
import { s } from '@/lib/strings';
import { SiteMark } from '@/components/DatastegBar';

/** The Glacier Masthead with the section of the current path marked active: Latest (articles and formats),
 *  Topics, About (which holds How we work and the Glossary). */
export function SiteMasthead({ lang, children }: { lang: Lang; children: ReactNode }) {
  const path = usePathname() ?? '';
  const base = `/${lang}`;
  const section = path.slice(base.length).split('/')[1] ?? '';
  const links = [
    { label: s(lang, 'nav.latest'), href: base, active: section === '' || section === 'a' || section === 'formats' },
    { label: s(lang, 'nav.topics'), href: `${base}/topics`, active: section === 'topics' },
    { label: s(lang, 'nav.about'), href: `${base}/about`, active: section === 'about' || section === 'method' || section === 'glossary' },
  ];
  return (
    <>
      <Masthead lang={lang} name={s(lang, 'wordmark')} mark={<SiteMark id="articles" size={24} className="ds-wordmark-mark" />} href={base} links={links} actions={children} />
      {/* Below 904px the Masthead hides its links: the same links in one scrolling row. */}
      <nav className="site-subnav" aria-label={t(lang, 'primaryNav')}>
        {links.map((l) => <a key={l.href} href={l.href} aria-current={l.active ? 'page' : undefined}>{l.label}</a>)}
      </nav>
    </>
  );
}
