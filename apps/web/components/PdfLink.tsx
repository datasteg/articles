import type { Lang } from '@glacier/i18n';
import type { Meta, PdfEdition } from '@/lib/content';
import { fileSize, s } from '@/lib/strings';

const fileName = (slug: string, lang: Lang) => `datasteg-${slug}-${lang}.pdf`;
const sizeOf = (p: PdfEdition, ui: Lang) => s(ui, 'pdf.size', { pages: p.pages, size: fileSize(p.bytes, ui) });

function DownloadIcon() {
  return <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 4v11" /><path d="M7.5 10.5 12 15l4.5-4.5" /><path d="M5 19.5h14" /></svg>;
}

/** The article header's PDF download (contracts/content.md § PDF), saved as datasteg-<slug>-<lang>.pdf. */
export function PdfButton({ pdf, slug, lang }: { pdf: PdfEdition; slug: string; lang: Lang }) {
  if (!pdf.url) return null;
  const size = sizeOf(pdf, lang);
  return (
    <a className="gl-btn gl-btn--secondary gl-btn--sm ac-pdf" href={pdf.url} download={fileName(slug, lang)} type="application/pdf"
      aria-label={`${s(lang, 'pdf.download')} (${size})`} title={size}>
      <DownloadIcon />{s(lang, 'pdf.button')}
    </a>
  );
}

/** Both editions' PDFs, under "Cite this article": English (12 pages, 1.1 MB) · Korean (11 pages, 1.7 MB). */
export function PdfEditions({ pdf, slug, lang }: { pdf: Meta['pdf']; slug: string; lang: Lang }) {
  const list = (['en', 'ko'] as const).flatMap((l) => (pdf?.[l]?.url ? [[l, pdf[l] as PdfEdition] as const] : []));
  if (!list.length) return null;
  return (
    <p className="ac-howtocite__pdf">
      <strong>{s(lang, 'pdf.title')}.</strong> {s(lang, 'pdf.ask')}{' '}
      {list.map(([l, p], i) => (
        <span key={l} className="ac-howtocite__pdflink">
          {i ? ' · ' : ''}<a className="gl-link" href={p.url} download={fileName(slug, l)} type="application/pdf">{s(lang, l === 'en' ? 'pdf.en' : 'pdf.ko')}</a>
          {' '}<span className="ac-howtocite__pdfsize">({sizeOf(p, lang)})</span>
        </span>
      ))}
    </p>
  );
}
