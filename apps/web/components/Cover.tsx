import type { Lang } from '@glacier/i18n';
import { coverCounts, type Article } from '@/lib/content';
import { plateLabel } from '@/lib/strings';

/** An article's cover in a story card (guides/covers.md): a flat drawing whose colours are palette classes, mapped
 *  to Glacier tokens in site.css so it follows the theme. Inlined from content (checked by artools and by the
 *  index before it gets here). Decorative: the card's title says what the article is. Under it, a plate with what
 *  the article is built on (indicators, papers, charts), counted from its content. */
export function Cover({ article, lang }: { article: Article; lang: Lang }) {
  const cover = article.cover;
  if (!cover) return null;
  const n = coverCounts(article);
  const items = (['indicators', 'papers', 'charts'] as const).filter((k) => n[k] > 0);
  return (
    <>
      <svg className="cover" viewBox={cover.viewBox} preserveAspectRatio="xMidYMid slice" aria-hidden focusable="false"
        dangerouslySetInnerHTML={{ __html: cover.svg }} />
      {items.length ? (
        <p className="cover-stats">
          {items.map((k) => <span key={k} className="cover-stat"><b>{n[k]}</b> <span>{plateLabel(lang, k, n[k])}</span></span>)}
        </p>
      ) : null}
    </>
  );
}
