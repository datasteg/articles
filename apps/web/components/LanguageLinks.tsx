'use client';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { LanguageSwitch } from '@glacier/ui';
import type { Lang } from '@glacier/i18n';

/** LanguageSwitch that links to the same page in the other language, keeping the query string
 *  (dashboard filters) and the anchor, and remembers the choice in the glacier-lang cookie. */
export function LanguageLinks({ lang }: { lang: Lang }) {
  const pathname = usePathname() ?? `/${lang}`;
  const [tail, setTail] = useState('');
  useEffect(() => {
    const update = () => setTail(window.location.search + window.location.hash);
    update();
    window.addEventListener('hashchange', update);
    window.addEventListener('popstate', update);
    return () => { window.removeEventListener('hashchange', update); window.removeEventListener('popstate', update); };
  }, [pathname]);
  const swap = (to: Lang) => pathname.replace(/^\/(en|ko)(?=\/|$)/, `/${to}`) + tail;
  const remember = (to: Lang) => () => { document.cookie = `glacier-lang=${to}; path=/; max-age=31536000; samesite=lax`; };
  return (
    <LanguageSwitch
      lang={lang}
      options={[
        { code: 'en', label: 'EN', href: swap('en'), onClick: remember('en') },
        { code: 'ko', label: '한국어', href: swap('ko'), onClick: remember('ko') },
      ]}
    />
  );
}
