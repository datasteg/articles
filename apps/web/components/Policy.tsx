import type { ReactNode } from 'react';
import { s } from '@/lib/strings';
import type { Lang } from '@glacier/i18n';

// The Privacy and Terms pages: a page head, then plain sections of prose. Text lives in each page, per language.

export type PolicyBlock = string | string[];
export interface PolicySection { id: string; h: string; body: PolicyBlock[] }
export interface PolicyDoc { title: string; dek: string; updated: string; sections: PolicySection[] }

/** Paragraph text with links: [text](https://…) and bare e-mail addresses. */
function Rich({ text }: { text: string }) {
  const out: ReactNode[] = [];
  const re = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|([\w.+-]+@[\w-]+(?:\.[\w-]+)+)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(m[1] ? <a key={m.index} href={m[2]}>{m[1]}</a> : <a key={m.index} href={`mailto:${m[3]}`}>{m[3]}</a>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return <>{out}</>;
}

export function Policy({ lang, doc }: { lang: Lang; doc: PolicyDoc }) {
  return (
    <>
      <header className="page-head">
        <p className="gl-kicker"><a className="page-head__up" href={`/${lang}/about`}>{s(lang, 'nav.about')}</a></p>
        <h1>{doc.title}</h1>
        <p className="dek">{doc.dek}</p>
      </header>
      <article className="gl-prose policy">
        <p className="policy__updated">{doc.updated}</p>
        {doc.sections.map((sec) => (
          <section key={sec.id} id={sec.id} aria-labelledby={`${sec.id}-h`}>
            <h2 id={`${sec.id}-h`}>{sec.h}</h2>
            {sec.body.map((b, i) => (Array.isArray(b)
              ? <ul key={i}>{b.map((li, j) => <li key={j}><Rich text={li} /></li>)}</ul>
              : <p key={i}><Rich text={b} /></p>))}
          </section>
        ))}
      </article>
    </>
  );
}
