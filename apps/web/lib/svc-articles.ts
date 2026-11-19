// The articles views behind /svc/v1: what the article, glossary and topic pages
// show, mapped to the public schema the datasteg API serves (readable names, not the content index's own keys). Built
// from lib/content.ts only, the published content index the pages use: nothing a page may not show leaves here.
// Facts the analysis blocked (meta.facts[].publishable false) are never served; source quotes pass through as
// published (one sentence per archive document, articles/config/sources.yaml). Korean comes only from the content and
// the site's string modules; every summary and note is English.
import type { Lang } from '@glacier/i18n';
import { t as gt } from '@glacier/i18n';
import { tx, type ChartSpec, type Txt } from '@articles/charts';
import { ARTICLES, BUILT_AT, GLOSSARY, PIPELINES, TOPICS, TOPIC_GROUPS, editionOf, editionsOf, getPipeline, type Article, type Block, type GlossaryTerm, type Source } from './content';
import { citationBibtex, citationText } from './citation';
import { figureNumbers } from './cites';
import { sortTerms } from './glossary';
import { s } from './strings';
import { plainText } from './text';

export const SITE = 'https://articles.datasteg.com';
/** The image version /health reports (APP_VERSION, inlined at build by next.config.ts). */
export const RELEASE = process.env.APP_VERSION ?? 'dev';
/** When the content index was built. */
export const BUILT = BUILT_AT ?? process.env.BUILD_TIME ?? '';
export const termsUrl = (lang: Lang) => `${SITE}/${lang}/terms`;
export const REUSE = 'Reuse: linking to an article and quoting short passages with a link back and the attribution in its citation are welcome; republishing an article, a chart or a video in full, or using them commercially, needs permission (datasteg@gmail.com). The data behind each chart belongs to the source named with it, and that source\'s terms apply to the data. Terms: ';

export type Cell = string | number | null;
export interface Table { columns: Array<{ id: string; label: string; unit?: string }>; rows: Cell[][] }

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
/** "23 October 2026". */
export function longDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return m ? `${d ? `${d} ` : ''}${MONTHS[m - 1]} ${y}` : String(y);
}

/** Cut at a word boundary, with an ellipsis. */
export function clip(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 1);
  const sp = cut.lastIndexOf(' ');
  return `${(sp > max * 0.6 ? cut.slice(0, sp) : cut).replace(/[\s,;:.]+$/, '')}…`;
}

export const plain = (x: string | null | undefined) => plainText(String(x ?? '')).replace(/\s+/g, ' ').trim();

/** Inline marks as Markdown: citations as source ids ([S3, S5]), glossary marks as their words; emphasis and links
 *  stay Markdown. */
export function md(x: string | null | undefined): string {
  return String(x ?? '')
    .replace(/\s*\[\[([^\]]+)\]\]/g, (_m: string, ids: string) => ` [${ids.split(',').map((v) => v.trim()).join(', ')}]`)
    .replace(/\(\(([^)|]+)(?:\|([^)]*))?\)\)/g, (_m: string, id: string, text: string) => text || id);
}

const cellOf = (v: unknown, lang: Lang): Cell => {
  if (v == null || v === '') return v === '' ? '' : null;
  if (typeof v === 'number' || typeof v === 'string') return v;
  if (typeof v === 'object') return tx(v as Txt, lang);
  return String(v);
};
const esc = (v: unknown) => String(v ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ');

// ------------------------------------------------------------------ envelope

export function envelope(view: string, lang: Lang, o: {
  page: string; summary: string; data: unknown; sources?: unknown[]; notes?: string[]; table?: Table; cursor?: string | null;
}) {
  return {
    app: 'articles', view, release: RELEASE, built: BUILT, page: o.page, terms: termsUrl(lang),
    sources: o.sources ?? [], summary: clip(o.summary.replace(/\s+/g, ' ').trim(), 600), data: o.data,
    ...(o.table ? { table: o.table } : {}),
    ...(o.notes?.length ? { notes: o.notes } : {}),
    ...(o.cursor ? { cursor: o.cursor } : {}),
  };
}

export const reuseNote = (lang: Lang) => REUSE + termsUrl(lang);

// ------------------------------------------------------------------ sources

/** One sources.json entry in the public schema. The newsroom's own fields (ref, dataset.publishable) stay out;
 *  `locate` (how to find the series on the provider's site) only where asked, as it is long. `brief`: the reference
 *  line only (id, kind, title, publisher, date, url, cite), for answers whose text already quotes the article. */
export function sourceOut(x: Source, lang: Lang, opts: { locate?: boolean; brief?: boolean } = {}) {
  if (opts.brief) {
    const b = { id: x.id, kind: x.kind, title: x.title, publisher: x.institution ?? null, date: x.date ?? null, url: x.url ?? null, cite: x.cite ? tx(x.cite, lang) : null };
    return Object.fromEntries(Object.entries(b).filter(([, v]) => v !== null && v !== undefined));
  }
  const ds = x.dataset;
  const out: Record<string, unknown> = {
    id: x.id, kind: x.kind, title: x.title, title_translated: x.titleTranslated?.[lang] ?? null, authors: x.authors ?? null,
    publisher: x.institution ?? null, series: x.series ?? null, number: x.number ?? null, date: x.date ?? null,
    url: x.url ?? null, pdf_url: x.pdfUrl ?? null, doi: x.doi ?? null,
    quote: x.quote?.text ? { text: x.quote.text, lang: x.quote.lang ?? 'en', locator: x.quote.locator ?? null } : null,
    dataset: ds ? {
      provider: ds.provider ?? null, key: ds.key ?? null, unit: ds.unit ?? null, frequency: ds.frequency ?? null,
      last_observation: ds.lastObservation ?? null, retrieved: ds.retrieved ?? null, attribution: ds.attribution ?? null,
      ...(opts.locate && ds.locate ? { locate: tx(ds.locate, lang) } : {}),
    } : null,
    cite: x.cite ? tx(x.cite, lang) : null, used_for: x.usedFor ? tx(x.usedFor, lang) : null,
  };
  return Object.fromEntries(Object.entries(out).filter(([, v]) => v !== null && v !== undefined));
}

// ------------------------------------------------------------------ lists

export const pageOf = (a: Article, lang: Lang) => `/${lang}/a/${a.slug}`;
const typeName = (a: Article, lang: Lang) => tx(getPipeline(a.meta.type)?.name, lang) || a.meta.type;

export function listItem(a: Article, lang: Lang) {
  const { ed, lang: el } = editionOf(a, lang);
  return {
    slug: a.slug, title: ed.title, kicker: ed.kicker, dek: plain(ed.dek), type: a.meta.type ?? 'explainer', type_name: typeName(a, lang),
    date: a.meta.date, updated: a.meta.updated ?? null, topics: a.meta.topics.map((t) => ({ id: t.id, label: tx(t.label, lang) })),
    countries: a.meta.countries ?? [], editions: editionsOf(a), edition: el, page: pageOf(a, lang),
  };
}

/** Every article type (config/pipelines), including those with no article yet. */
export const ARTICLE_TYPES = [...new Set([...PIPELINES.map((p) => p.id), ...ARTICLES.map((a) => a.meta.type ?? 'explainer')])];

// ------------------------------------------------------------------ one article

function tableMd(b: Extract<Block, { type: 'table' }>): string {
  const head = `| ${b.columns.map((c) => esc(c.label)).join(' | ')} |`;
  const rule = `| ${b.columns.map((c) => (c.align === 'right' ? '---:' : '---')).join(' | ')} |`;
  const rows = b.rows.map((r) => `| ${b.columns.map((c) => esc(r[c.key])).join(' | ')} |`);
  return [b.caption ? `**${md(b.caption)}**${b.source ? ` [${b.source}]` : ''}` : '', head, rule, ...rows].filter(Boolean).join('\n');
}

function blockMd(b: Block, a: Article, lang: Lang, figs: Map<string, number>): string {
  switch (b.type) {
    case 'p': return md(b.text);
    case 'list': return b.items.map((x) => `- ${md(x)}`).join('\n');
    case 'quote': {
      const src = b.cite ? a.sources.find((x) => x.id === b.cite) : undefined;
      const who = src ? [src.institution ?? src.series, src.date?.slice(0, 4)].filter(Boolean).join(', ') : '';
      return `> “${b.text}”${who || b.cite ? `\n> — ${who}${b.cite ? ` [${b.cite}]` : ''}` : ''}`;
    }
    case 'table': return tableMd(b);
    case 'figure': {
      const c = a.charts[b.chart];
      const n = figs.get(b.chart);
      const what = c ? tx(c.headline ?? c.title, lang) : '';
      return `[${s(lang, 'figure', { n: n ?? '' })}${what ? `: ${md(what)}` : ''} (chart ${b.chart})]`;
    }
    default: return '';
  }
}

/** The article's charts: id, form, figure number, titles and the public CSV. */
function chartList(a: Article, lang: Lang) {
  const { ed } = editionOf(a, lang);
  const figs = figureNumbers(ed);
  return (a.meta.charts ?? []).filter((id) => a.charts[id]).map((id) => {
    const c = a.charts[id] as ChartSpec & { csvUrl?: string };
    return { id, form: c.form, figure: figs.get(id) ?? null, title: tx(c.title, lang) || null, headline: tx(c.headline, lang) || null, csv: c.csvUrl ? SITE + c.csvUrl : null };
  });
}

export function articleData(a: Article, lang: Lang, section?: string) {
  const { ed, lang: el, fallback } = editionOf(a, lang);
  const figs = figureNumbers(ed);
  const c = a.meta.citation;
  const secs = ed.sections.filter((x) => !section || x.id === section);
  return {
    slug: a.slug, edition: el, fallback, type: a.meta.type ?? 'explainer', type_name: typeName(a, el), date: a.meta.date, updated: a.meta.updated ?? null,
    topics: a.meta.topics.map((t) => ({ id: t.id, label: tx(t.label, el) })), countries: a.meta.countries ?? [], jel: a.meta.jel ?? [],
    read_minutes: a.meta.readTime?.[el] ?? null,
    kicker: ed.kicker, title: ed.title, dek: md(ed.dek), byline: ed.byline ?? 'datasteg',
    key_numbers: (ed.keyNumbers ?? []).map((k) => ({ value: k.value, label: k.label, sources: k.cite ?? [] })),
    findings: (ed.findings ?? []).map(md),
    question: ed.question ? { asked: ed.question.asked, looked_at: ed.question.lookedAt, premise_note: ed.question.premiseNote ?? null } : null,
    sections: secs.map((sec) => ({
      id: sec.id, heading: sec.heading, summary: sec.summary ? plain(sec.summary) : null,
      text: sec.blocks.map((b) => blockMd(b, a, el, figs)).filter(Boolean).join('\n\n'),
      charts: sec.blocks.flatMap((b) => (b.type === 'figure' ? [b.chart] : [])),
    })),
    ...(section ? { section_ids: ed.sections.map((x) => x.id) } : {}),
    insight: ed.insight?.text ? { label: ed.insight.label ?? gt(el, 'ourRead'), text: md(ed.insight.text) } : null,
    terms: a.terms.filter((x) => GLOSSARY[x.id]).map((x) => ({ id: x.id, term: tx(GLOSSARY[x.id].term, el), definition: tx(GLOSSARY[x.id].definition, el), context: x.context ? tx(x.context, el) : null })),
    charts: chartList(a, el),
    disclaimer: ed.disclaimer ?? null,
    citation: c ? { text: citationText(c, el), bibtex: citationBibtex(c, a.slug, el), url: tx(c.url, el) } : null,
    corrections: (a.meta.corrections ?? []).map((x) => ({ date: x.date, text: tx(x.text, el) })),
    pdf: a.meta.pdf?.[el]?.url ? SITE + a.meta.pdf[el]!.url : null,
  };
}

/** English, for any edition: the title, type and date, the dek and the first finding. */
export function articleSummary(a: Article): string {
  const { ed } = editionOf(a, 'en');
  const first = ed.findings?.[0] ? ` First finding: ${plain(ed.findings[0])}` : '';
  return `“${ed.title}”, a datasteg ${typeName(a, 'en').toLowerCase()} of ${longDate(a.meta.date)}${a.meta.updated ? `, updated ${longDate(a.meta.updated)}` : ''}. ${plain(ed.dek)}${first}`;
}

/** The whole edition as readable Markdown (the fetch tool's text), at most `max` characters: what does not fit
 *  (the references first, then the terms, then sections from the end) is named in a closing line with the page. */
export function articleMarkdown(a: Article, lang: Lang, max = 20000): { text: string; cut: string[] } {
  const { ed, lang: el } = editionOf(a, lang);
  const figs = figureNumbers(ed);
  const parts: Array<{ key: string; prio: number; text: string }> = [];
  const add = (key: string, prio: number, text: string) => { if (text.trim()) parts.push({ key, prio, text }); };
  add('head', 0, [`# ${ed.title}`, `${ed.kicker} · ${a.meta.date} · ${ed.byline ?? 'datasteg'}`, md(ed.dek)].join('\n\n'));
  if (ed.keyNumbers?.length) add(s(el, 'keyNumbers'), 0, `## ${s(el, 'keyNumbers')}\n\n${ed.keyNumbers.map((k) => `- **${k.value}** ${k.label}${k.cite?.length ? ` [${k.cite.join(', ')}]` : ''}`).join('\n')}`);
  add(s(el, 'findingsTitle'), 0, `## ${s(el, 'findingsTitle')}\n\n${(ed.findings ?? []).map((f) => `- ${md(f)}`).join('\n')}`);
  if (ed.question) {
    add(s(el, 'question'), 0, [`## ${s(el, 'question')}`, `**${s(el, 'ourQuestion')}.** ${ed.question.asked}`, `**${s(el, 'lookedAt')}.** ${ed.question.lookedAt}`,
      ed.question.premiseNote ? `**${s(el, 'premiseNote')}.** ${ed.question.premiseNote}` : ''].filter(Boolean).join('\n\n'));
  }
  ed.sections.forEach((sec, i) => add(sec.heading, 1 + i / 1000, `## ${sec.heading}\n\n${sec.blocks.map((b) => blockMd(b, a, el, figs)).filter(Boolean).join('\n\n')}`));
  if (ed.insight?.text) add(ed.insight.label ?? gt(el, 'ourRead'), 2, `## ${ed.insight.label ?? gt(el, 'ourRead')}\n\n${md(ed.insight.text)}`);
  const terms = a.terms.filter((x) => GLOSSARY[x.id]);
  if (terms.length) add(s(el, 'termsTitle'), 3, `## ${s(el, 'termsTitle')}\n\n${terms.map((x) => `- **${tx(GLOSSARY[x.id].term, el)}**: ${tx(GLOSSARY[x.id].definition, el)}${x.context ? ` ${tx(x.context, el)}` : ''}`).join('\n')}`);
  if (a.sources.length) add(s(el, 'references'), 4, `## ${s(el, 'references')}\n\n${a.sources.map((x) => `- [${x.id}] ${x.cite ? tx(x.cite, el) : x.title}${x.url ? ` ${x.url}` : ''}`).join('\n')}`);
  if (a.meta.corrections?.length) add(s(el, 'corrections'), 2, `## ${s(el, 'corrections')}\n\n${a.meta.corrections.map((x) => `- ${x.date}: ${tx(x.text, el)}`).join('\n')}`);
  if (ed.disclaimer) add(s(el, 'disclaimer'), 2, `**${s(el, 'disclaimer')}.** ${ed.disclaimer}`);
  const tail = [a.meta.citation ? `## ${s(el, 'cite.title')}\n\n${citationText(a.meta.citation, el)}` : '', `${s(el, 'nav.terms')}: ${termsUrl(el)}`].filter(Boolean).join('\n\n');
  const url = `${SITE}${pageOf(a, el)}`;
  const room = max - tail.length - 400;    // the closing line, when something is left out
  const keep = new Set<number>();
  let used = 0;
  let sectionsStopped = false;
  for (const i of parts.map((_, j) => j).sort((x, y) => parts[x].prio - parts[y].prio)) {
    const p = parts[i];
    const isSection = p.prio >= 1 && p.prio < 2;
    if (isSection && sectionsStopped) continue;
    if (used + p.text.length + 2 <= room) { keep.add(i); used += p.text.length + 2; } else if (isSection) sectionsStopped = true;
  }
  const cut = parts.filter((_, i) => !keep.has(i)).map((p) => p.key);
  // the note goes where the text first leaves something out, so the reader sees the gap where it is
  const note = `[Not included here, to keep this text within ${max.toLocaleString('en-GB')} characters: ${clip(cut.join('; '), 250)}. The full article is at ${url}]`;
  const first = parts.findIndex((_, i) => !keep.has(i));
  const body = parts.flatMap((p, i) => [...(i === first ? [note] : []), ...(keep.has(i) ? [p.text] : [])]);
  return { text: [...body, tail].join('\n\n'), cut };
}

// ------------------------------------------------------------------ facts and charts

export function publishedFacts(a: Article) {
  return (a.meta.facts ?? []).filter((f) => f.publishable === true);
}

export function factOut(f: NonNullable<Article['meta']['facts']>[number]) {
  return { id: f.id, value: f.value, unit: f.unit ?? null, period: f.period ?? null, sources: f.sources ?? [], ...(f.series?.length ? { series: f.series } : {}) };
}

export function chartOut(a: Article, id: string, lang: Lang) {
  const { ed } = editionOf(a, lang);
  const c = a.charts[id] as ChartSpec & { csvUrl?: string };
  const m = c.meta ?? {};
  return {
    id, form: c.form, figure: figureNumbers(ed).get(id) ?? null,
    headline: tx(c.headline, lang) || null, title: tx(c.title, lang) || null, subtitle: tx(c.subtitle, lang) || null,
    how_to_read: c.howToRead ? tx(c.howToRead, lang) : null, notes: (c.notes ?? []).map((n) => tx(n, lang)),
    meta: {
      sources: m.sources ?? [], provider: m.provider ?? null, keys: m.keys ?? [], definition: m.definition ? tx(m.definition, lang) : null,
      calculation: m.calculation ? tx(m.calculation, lang) : null, span: m.span ?? null, last_observation: m.lastObservation ?? null,
      retrieved: m.retrieved ?? null, licence: m.licence ?? null, attribution: m.attribution ? tx(m.attribution, lang) : null,
    },
    csv: c.csvUrl ? SITE + c.csvUrl : null,
  };
}

/** The chart's data: its table (the rows of the public CSV /data/<slug>/<chart>.csv, labels in the asked language),
 *  or for key-number tiles, the tiles. */
export function chartTable(c: ChartSpec, lang: Lang): Table {
  if (c.table?.columns?.length) {
    const cols = c.table.columns;
    return { columns: cols.map((x) => ({ id: x.key, label: tx(x.label, lang) || x.key })), rows: (c.table.rows ?? []).map((r) => cols.map((x) => cellOf(r[x.key], lang))) };
  }
  if (c.tiles?.length) {
    return {
      columns: [{ id: 'label', label: 'Label' }, { id: 'value', label: 'Value' }, { id: 'note', label: 'Note' }, { id: 'sources', label: 'Sources' }],
      rows: c.tiles.map((t) => [tx(t.label, lang), tx(t.value, lang), t.note ? tx(t.note, lang) : null, (t.cite ?? []).join(' ')]),
    };
  }
  return { columns: [{ id: 'note', label: 'Note' }], rows: [] };
}

// ------------------------------------------------------------------ glossary and topics

export function termOut(g: GlossaryTerm, lang: Lang) {
  const other: Lang = lang === 'ko' ? 'en' : 'ko';
  const alt = typeof g.term === 'string' ? null : g.term[other] ?? null;
  return {
    id: g.id, term: tx(g.term, lang), [`term_${other}`]: alt && alt !== tx(g.term, lang) ? alt : null, definition: tx(g.definition, lang),
    topics: g.topicIds ?? [], see: g.see ?? [], articles: g.articles ?? [], page: `/${lang}/glossary/${g.id}`,
  };
}

export const sortedTerms = (lang: Lang) => sortTerms(Object.values(GLOSSARY), lang);

export function topicGroups(lang: Lang) {
  const known = new Set(TOPIC_GROUPS.map((g) => g.id));
  const topic = (x: (typeof TOPICS)[number]) => ({ id: x.id, label: tx(x.label, lang), articles: x.articles, terms: x.terms.length, page: `/${lang}?topic=${x.id}` });
  const out = TOPIC_GROUPS.map((g) => ({ id: g.id, label: tx(g.label, lang), topics: TOPICS.filter((x) => x.group === g.id).map(topic) }));
  const rest = TOPICS.filter((x) => !x.group || !known.has(x.group));
  if (rest.length) out.push({ id: 'more', label: 'More', topics: rest.map(topic) });
  return out.filter((g) => g.topics.length);
}

// ------------------------------------------------------------------ search

const norm = (x: string) => x.normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim();
const tokens = (q: string) => [...new Set(norm(q).split(/[\s,.;:!?"'“”‘’()[\]{}<>/\\|]+/).filter((t) => t.length >= 2 || /[\u3131-\u318E\uAC00-\uD7A3\u4E00-\u9FFF]/.test(t)))];

function score(q: string, exact: string[], fields: Array<[string, number]>): number {
  const nq = norm(q);
  if (!nq) return 0;
  if (exact.some((x) => norm(x) === nq)) return 1;
  const toks = tokens(q);
  if (!toks.length) return 0;
  const hay = fields.map(([text, w]) => [norm(text), w] as const);
  let sum = 0;
  for (const t of toks) sum += Math.max(0, ...hay.filter(([h]) => h.includes(t)).map(([, w]) => w));
  let sc = 0.95 * (sum / toks.length);
  const phrase = hay.filter(([h]) => toks.length > 1 && h.includes(nq)).map(([, w]) => w);
  if (phrase.length) sc = Math.max(sc, 0.9 * Math.max(...phrase) + 0.05);
  return Math.round(Math.min(sc, 0.99) * 1000) / 1000;
}

export function search(q: string, lang: Lang, limit: number) {
  const items: Array<{ id: string; kind: string; title: string; snippet: string; page: string; score: number }> = [];
  for (const a of ARTICLES) {
    const eds = editionsOf(a).map((l) => a.editions[l]).filter(Boolean) as NonNullable<Article['editions']['en']>[];
    const termNames = a.terms.flatMap((x) => (GLOSSARY[x.id] ? [tx(GLOSSARY[x.id].term, 'en'), tx(GLOSSARY[x.id].term, 'ko')] : []));
    const sc = score(q, [a.slug, ...eds.map((e) => plain(e.title))], [
      ...eds.flatMap((e) => [[plain(e.title), 1], [plain(e.kicker), 0.8], [plain(e.dek), 0.7], [e.findings.map(plain).join(' '), 0.5]] as Array<[string, number]>),
      [termNames.join(' '), 0.6], [a.slug.replace(/-/g, ' '), 0.9],
    ]);
    if (sc > 0) {
      const { ed } = editionOf(a, lang);
      items.push({ id: `article:${a.slug}`, kind: 'article', title: ed.title, snippet: clip(plain(ed.dek), 220), page: pageOf(a, lang), score: sc });
    }
  }
  for (const g of Object.values(GLOSSARY)) {
    const names = [tx(g.term, 'en'), tx(g.term, 'ko'), g.id];
    const sc = score(q, names, [[names.join(' '), 1], [`${tx(g.definition, 'en')} ${tx(g.definition, 'ko')}`, 0.5]]);
    if (sc > 0) items.push({ id: `term:${g.id}`, kind: 'term', title: tx(g.term, lang), snippet: clip(tx(g.definition, lang), 220), page: `/${lang}/glossary/${g.id}`, score: sc === 1 ? 1 : Math.round(sc * 0.97 * 1000) / 1000 });
  }
  return items.sort((x, y) => y.score - x.score || x.id.localeCompare(y.id)).slice(0, limit);
}

// ------------------------------------------------------------------ parameters

export function intParam(url: URL, name: string, dflt: number, lo: number, hi: number): number | string {
  const v = url.searchParams.get(name);
  if (v == null || v === '') return dflt;
  if (!/^\d+$/.test(v) || Number(v) < lo || Number(v) > hi) return `${name} must be a whole number from ${lo} to ${hi}; got "${clip(v, 40)}".`;
  return Number(v);
}

export const SLUG = /^[a-z0-9][a-z0-9-]{0,99}$/;
