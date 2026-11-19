import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import '@glacier/tokens/tokens.css';
import '@glacier/fonts';
import 'pretendard/dist/web/static/pretendard-dynamic-subset.css';
import '@glacier/ui/glacier.css';
import '@articles/charts/charts.css';
import './studio.css';

// The video's slides use the site's dark theme, whatever the machine's setting.
export const metadata: Metadata = { title: 'datasteg studio', robots: { index: false, follow: false } };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="dark">
      <body className="vs-body">{children}</body>
    </html>
  );
}
