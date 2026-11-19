import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { notFound } from 'next/navigation';
import '@glacier/tokens/tokens.css';
import '@glacier/fonts';
// Static faces of the same families (print.css puts them first): Chromium embeds a variable font in a PDF as Type 3
// glyphs and a static one as a TrueType subset, which every PDF viewer and printer renders best. Noto Serif KR is
// static already (@glacier/fonts).
import '@fontsource/hanken-grotesk/400.css';
import '@fontsource/hanken-grotesk/500.css';
import '@fontsource/hanken-grotesk/600.css';
import '@fontsource/hanken-grotesk/700.css';
import '@fontsource/source-serif-4/400.css';
import '@fontsource/source-serif-4/400-italic.css';
import '@fontsource/source-serif-4/600.css';
import '@fontsource/source-serif-4/600-italic.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import 'pretendard/dist/web/static/pretendard-dynamic-subset.css';
import '@glacier/ui/glacier.css';
import '@articles/charts/charts.css';
import '../../print.css';
import { isLang, LANGS } from '@glacier/i18n';

// The PDF edition's page: its own root layout, without the site's header, footer or theme switch (always light).
// `artools pdf` prints /print/<lang>/<slug> with Chromium (pipeline/artools/pdf.py); readers download the PDF.
export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.map((lang) => ({ lang }));
}

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function PrintLayout({ children, params }: { children: ReactNode; params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  return (
    <html lang={lang} data-theme="light">
      <body className="pf-page">{children}</body>
    </html>
  );
}
