import type { Metadata } from 'next';
import { GLOSSARY } from '@/lib/content';
import { Glyph, type GlyphName } from '@/components/Glyph';
import { langOf } from '@/lib/page';
import { s } from '@/lib/strings';

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const lang = await langOf(params);
  return { title: s(lang, 'nav.about') };
}

/** About: the hub for what isn't an article (How we work, the Glossary, corrections, not advice). */
export default async function About({ params }: { params: Promise<{ lang: string }> }) {
  const lang = await langOf(params);
  const base = `/${lang}`;
  const cards: Array<{ icon: GlyphName; title: string; text: string; href?: string }> = [
    { icon: 'steps', title: s(lang, 'nav.method'), text: s(lang, 'about.method'), href: `${base}/method` },
    { icon: 'book', title: s(lang, 'nav.glossary'), text: s(lang, 'about.glossary', { n: Object.keys(GLOSSARY).length }), href: `${base}/glossary` },
    { icon: 'correct', title: s(lang, 'corrections'), text: s(lang, 'about.corrections') },
    { icon: 'institution', title: s(lang, 'about.advice.h'), text: s(lang, 'about.advice') },
    { icon: 'person', title: s(lang, 'about.privacy.h'), text: s(lang, 'about.privacy'), href: `${base}/privacy` },
  ];
  return (
    <>
      <header className="page-head">
        <p className="gl-kicker">{s(lang, 'nav.about')}</p>
        <h1>{s(lang, 'about.title')}</h1>
        <p className="dek">{s(lang, 'about.dek')}</p>
      </header>
      <ul className="hub">
        {cards.map((c) => (
          <li key={c.title} className="hub__card">
            <span className="hub__icon"><Glyph name={c.icon} size={22} /></span>
            <h2 className="hub__title">{c.href ? <a href={c.href}>{c.title}</a> : c.title}</h2>
            <p className="hub__text">{c.text}</p>
            {c.href ? <span className="hub__go" aria-hidden><Glyph name="arrow" size={18} /></span> : null}
          </li>
        ))}
      </ul>
    </>
  );
}
