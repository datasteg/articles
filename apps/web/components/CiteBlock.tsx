import type { Lang } from '@glacier/i18n';
import { CopyButton } from '@/components/CopyButton';
import { PdfEditions } from '@/components/PdfLink';
import { citationBibtex, citationText } from '@/lib/citation';
import type { Citation, Meta } from '@/lib/content';
import { s } from '@/lib/strings';

/** "Cite this article", near the end of every article: a request to cite, the citation with a copy button, BibTeX
 *  under a fold, and the PDF editions. From meta.citation, which `artools publish` stamps, and meta.pdf, which
 *  `artools pdf` writes (contracts/content.md § Citation, § PDF). */
export function CiteBlock({ citation, slug, lang, pdf }: { citation: Citation; slug: string; lang: Lang; pdf?: Meta['pdf'] }) {
  const text = citationText(citation, lang);
  const bib = citationBibtex(citation, slug, lang);
  return (
    <section id="cite" className="ac-narrow ac-howtocite" aria-labelledby="cite-h">
      <h2 id="cite-h" className="ac-h2">{s(lang, 'cite.title')}</h2>
      <p className="ac-howtocite__ask">{s(lang, 'cite.ask')}</p>
      <p className="ac-howtocite__text">{text}</p>
      <div className="ac-howtocite__actions">
        <CopyButton text={text} label={s(lang, 'cite.copy')} done={s(lang, 'cite.copied')} />
      </div>
      <details className="ac-howtocite__bib">
        <summary>{s(lang, 'cite.bibtex')}</summary>
        <pre><code>{bib}</code></pre>
        <CopyButton text={bib} label={s(lang, 'cite.copyBibtex')} done={s(lang, 'cite.copied')} />
      </details>
      <PdfEditions pdf={pdf} slug={slug} lang={lang} />
    </section>
  );
}
