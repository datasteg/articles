'use client';
import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { t, type Lang } from '@glacier/i18n';

/** Quiet icon button in the Masthead. The theme itself is set before first paint by THEME_SCRIPT. */
export function ThemeToggle({ lang }: { lang: Lang }) {
  const [theme, setTheme] = useState<'light' | 'dark' | null>(null);
  useEffect(() => {
    setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light');
  }, []);
  const next = theme === 'dark' ? 'light' : 'dark';
  function toggle() {
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('glacier-theme', next); } catch { /* private mode: the choice lasts this page only */ }
    setTheme(next);
  }
  const label = t(lang, next === 'dark' ? 'themeToDark' : 'themeToLight');
  return (
    <button type="button" className="gl-btn gl-btn--quiet" onClick={toggle} aria-label={label} title={label}>
      {theme === 'dark' ? <Sun size={20} strokeWidth={1.5} aria-hidden /> : <Moon size={20} strokeWidth={1.5} aria-hidden />}
    </button>
  );
}

/** Runs in <head> before the first paint: ?theme=dark|light (used for screenshots), else the saved choice, else the system setting. */
export const THEME_SCRIPT = `(function(){var t;try{t=new URLSearchParams(location.search).get('theme')}catch(e){}if(t!=='light'&&t!=='dark'){try{t=localStorage.getItem('glacier-theme')}catch(e){}}if(t!=='light'&&t!=='dark'){t=window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}document.documentElement.setAttribute('data-theme',t)})();`;
