'use client';
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { LANG_COOKIE } from '@glacier/i18n';

/** On an English page, a one-line offer of the Korean page, for a browser that lists Korean and a reader who hasn't
 *  chosen a language yet. Following it or closing it saves the choice (the glacier-lang cookie), so it shows once.
 *  A URL that names a language is never redirected: a shared /en/ link opens what was shared. */
export function LanguageHint() {
  const pathname = usePathname() ?? '/en';
  const [href, setHref] = useState<string | null>(null);
  useEffect(() => {
    const chosen = document.cookie.split(';').some((c) => c.trim().startsWith(`${LANG_COOKIE}=`));
    const langs = navigator.languages?.length ? navigator.languages : [navigator.language];
    const korean = langs.some((l) => l?.toLowerCase().startsWith('ko'));
    setHref(!chosen && korean ? pathname.replace(/^\/en(?=\/|$)/, '/ko') + window.location.search + window.location.hash : null);
  }, [pathname]);
  if (!href) return null;
  const remember = (lang: string) => { document.cookie = `${LANG_COOKIE}=${lang}; path=/; max-age=31536000; samesite=lax`; };
  return (
    <div className="lang-hint" lang="ko" role="note">
      <p>이 페이지는 한국어로도 볼 수 있습니다. <a href={href} hrefLang="ko" onClick={() => remember('ko')}>한국어로 보기 →</a></p>
      <button type="button" aria-label="닫기" onClick={() => { remember('en'); setHref(null); }}>×</button>
    </div>
  );
}
