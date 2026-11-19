import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import { notFound } from 'next/navigation';
import '@glacier/tokens/tokens.css';
import '@glacier/ui/glacier.css';
import '@articles/charts/charts.css';
import '../site.css';
import '../article.css';
// the datasteg type (www's fonts, family/fonts.ts), loaded last: it points Glacier's font tokens at Newsreader, Libre Franklin and JetBrains Mono
import '@/lib/ds-fonts';
import { DatastegBar } from '@/components/DatastegBar';
import { Footer } from '@glacier/ui';
import { isLang, LANGS, t, type Lang } from '@glacier/i18n';
import { Counter } from '@/components/Counter';
import { LanguageHint } from '@/components/LanguageHint';
import { LanguageLinks } from '@/components/LanguageLinks';
import { SiteHeader } from '@/components/SiteHeader';
import { SiteMasthead } from '@/components/SiteMasthead';
import { SocialLinks } from '@/components/SocialLinks';
import { THEME_SCRIPT, ThemeToggle } from '@/components/ThemeToggle';
import { IS_PREVIEW } from '@/lib/content';
import { COUNT_SCRIPT } from '@/lib/count';
import { s } from '@/lib/strings';

export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.map((lang) => ({ lang }));
}

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  const l: Lang = isLang(lang) ? lang : 'en';
  return {
    // Absolute URLs for og:image and og:url, which X and LinkedIn need.
    metadataBase: new URL('https://articles.datasteg.com'),
    title: { default: 'datasteg articles', template: '%s — datasteg' },
    description: s(l, 'site.description'),
    // Open to search engines since 28 Oct 2026, except a preview build of drafts.
    robots: IS_PREVIEW ? { index: false, follow: false } : { index: true, follow: true },
    // Each page's hreflang twins are in /sitemap.xml; the home page and articles also name them here.
    openGraph: { locale: l === 'ko' ? 'ko_KR' : 'en_GB', siteName: 'datasteg' },
  };
}

export default async function LangLayout({ children, params }: { children: ReactNode; params: Promise<{ lang: string }> }) {
  const { lang: raw } = await params;
  if (!isLang(raw)) notFound();
  const lang: Lang = raw;
  const base = `/${lang}`;
  return (
    <html lang={lang} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        {/* Visitor counting without cookies (About § Privacy). Production builds only. */}
        {process.env.NODE_ENV === 'production'
          ? <script async src={COUNT_SCRIPT.src} data-goatcounter={COUNT_SCRIPT.endpoint} data-goatcounter-settings={COUNT_SCRIPT.settings} />
          : null}
      </head>
      <body>
        <Counter />
        <a className="skip-link" href="#main">{t(lang, 'skip')}</a>
        <DatastegBar lang={lang} site="articles" />
        <SiteHeader>
          <SiteMasthead lang={lang}>
            <LanguageLinks lang={lang} />
            <ThemeToggle lang={lang} />
          </SiteMasthead>
        </SiteHeader>
        {lang === 'en' ? <LanguageHint /> : null}
        <main id="main" tabIndex={-1}>{children}</main>
        <Footer
          lang={lang}
          name="datasteg"
          href={base}
          languageSwitch={<LanguageLinks lang={lang} />}
          links={[
            { label: s(lang, 'nav.latest'), href: base },
            { label: s(lang, 'nav.topics'), href: `${base}/topics` },
            { label: s(lang, 'nav.method'), href: `${base}/method` },
            { label: s(lang, 'nav.glossary'), href: `${base}/glossary` },
            { label: s(lang, 'nav.about'), href: `${base}/about` },
            { label: s(lang, 'nav.privacy'), href: `${base}/privacy` },
            { label: s(lang, 'nav.terms'), href: `${base}/terms` },
          ]}
          note={<><span>{`articles.datasteg.com · ${process.env.APP_VERSION}`}</span><SocialLinks lang={lang} /></>}
        />
      </body>
    </html>
  );
}
