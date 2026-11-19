import type { Lang } from '@glacier/i18n';
import { s } from '@/lib/strings';

/** The search field at the top of the home page's rail (and in the phone row above the feed). Search isn't built
 *  yet: the field is read-only and its help line says so. When search ships, this becomes
 *  <form role="search" action="/<lang>/search"> with the same look. */
export function SearchBox({ lang, id, short = false }: { lang: Lang; id: string; short?: boolean }) {
  return (
    <div className="site-search">
      <label className="gl-visually-hidden" htmlFor={id}>{s(lang, 'search.label')}</label>
      <div className="site-search__field">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden focusable="false">
          <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
        </svg>
        <input id={id} type="search" readOnly aria-disabled="true" aria-describedby={`${id}-help`} placeholder={s(lang, 'search.placeholder')} />
      </div>
      <p id={`${id}-help`} className="site-search__help">{s(lang, short ? 'search.helpShort' : 'search.help')}</p>
    </div>
  );
}
