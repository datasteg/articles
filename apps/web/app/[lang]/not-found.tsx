'use client';
import { usePathname } from 'next/navigation';
import { EmptyState, Button } from '@glacier/ui';
import { t } from '@glacier/i18n';

export default function NotFound() {
  const lang = usePathname()?.startsWith('/ko') ? 'ko' : 'en';
  return (
    <div className="nf">
      <h1 className="gl-visually-hidden">{t(lang, 'notFound.title')}</h1>
      <EmptyState lang={lang} title={t(lang, 'notFound.title')} body={t(lang, 'notFound.body')}
        action={<Button variant="secondary" href={`/${lang}`}>{t(lang, 'notFound.home')}</Button>} />
    </div>
  );
}
