// Content registry. scripts/build-content-index.mjs reads CONTENT_DIR (default content/) at build time and
// writes generated/content.json; pages are generated statically from it, and the server never reads
// content files at run time (the container's file system is read-only). Format: contracts/content.md.
import type { Lang } from '@glacier/i18n';
import { tx, type ChartSpec, type Txt } from '@articles/charts';
import data from '../generated/content.json';

export type { Txt };
export interface Topic { id: string; label: Txt }
export interface Correction { date: string; text: Txt }
export interface Meta {
  slug: string; type: string; date: string; updated: string | null; editions: Lang[];
  topics: Topic[]; jel: string[]; countries: string[]; readTime: Partial<Record<Lang, number>>;
  charts: string[];
  /** Every fact the run computed; `publishable` false = blocked by the analysis (never served), `sources` = sources.json ids,
   *  `series` = the series of a fact whose sources the article doesn't cite (contracts/content.md). */
  facts?: Array<{ id: string; value: number | string; unit?: string; period?: string; publishable?: boolean; sources?: string[]; series?: Array<{ provider?: string; key?: string }> }>;
  pipeline?: { id: string; version?: string };
  run?: { id: string; skills?: Record<string, string>; models?: string[]; steps?: Record<string, StepStats>; gates?: Record<string, { at?: string | null; by?: string | null }> };
  terms?: ArticleTerm[];
  /** The list's picture: cover.svg beside meta.json (guides/covers.md). */
  cover?: { file: string; alt?: Txt | null } | null;
  review: { editor: string | null; approved: string | null };
  /** How readers should cite the article, stamped by `artools publish` from config/editorial.yaml (contracts/content.md). */
  citation?: Citation | null;
  /** The PDF edition of each language, printed by `artools pdf` (contracts/content.md § PDF); the index adds each url. */
  pdf?: Partial<Record<Lang, PdfEdition>> | null;
  /** A data note's data download (data/data.zip), served as /data/<slug>/datasteg-<slug>-data.zip; the index adds the url. */
  download?: { file: string; bytes: number; url?: string } | null;
  corrections: Correction[];
  /** What the article drew on, stamped by `artools publish` (contracts/content.md § What the article drew on); read by
   * the portal's Data chart, not shown here. The apps whose pages or archive documents it cites, each with the number
   * of distinct sources that put it there, and what its run fetched from statistics APIs per provider folder. */
  draws_on?: FamilyApp[];
  draws_on_evidence?: Partial<Record<FamilyApp, number>>;
  fetch?: Record<string, FetchVolume>;
}
export type FamilyApp = 'money-flow' | 'trade-flow' | 'global-network' | 'open-research';
/** One provider's fetch: series (catalog entries with their CSV), data rows (header excluded) and CSV bytes. */
export interface FetchVolume { series: number; rows: number; bytes: number }
export interface Citation { author: Txt; publisher: Txt; date: string; title: Txt; url: Txt }
export interface PdfEdition { file: string; pages: number; bytes: number; made?: string; url?: string }
/** Counts from the run, drawn under a step in the article's pipeline diagram (contracts/content.md). */
export type StepStats = Record<string, number | string[] | Record<string, number> | undefined>;
export interface ArticleTerm { id: string; context?: Txt | null }
export interface KeyNumber { value: string; label: string; cite?: string[] }
export type Block =
  | { type: 'p'; text: string }
  | { type: 'figure'; chart: string }
  | { type: 'table'; caption?: string; columns: Array<{ key: string; label: string; align?: 'left' | 'right' }>; rows: Array<Record<string, string | number>>; source?: string }
  | { type: 'list'; items: string[] }
  | { type: 'quote'; text: string; cite?: string };
export interface Section { id: string; heading: string; blocks: Block[]; /** one sentence for the contents list */ summary?: string }
export interface Edition {
  kicker: string; title: string; dek: string; byline?: string;
  keyNumbers?: KeyNumber[]; findings: string[];
  question?: { asked: string; lookedAt: string; premiseNote?: string | null };
  sections: Section[];
  insight?: { label?: string; text: string } | null;
  disclaimer?: string;
  /** "Get the data" (data notes): each datasteg view the note read, its page and the API call for the same table,
   *  built by code (pipeline/artools/desk/reproduce.py). Words are per edition; URLs and code are the same in both. */
  reproduce?: Reproduce | null;
  /** "Why this note" (data notes): what is new today and why these economies, under the dek; the label travels with
   *  the edition so qkr drafts its Korean with the rest of the note. */
  whyNow?: string | null;
  whyNowLabel?: string | null;
}
export interface Reproduce {
  heading: string; intro: string; note?: string | null; docs?: string;
  items: Array<{ label: string; app: string; page?: string | null; api: string; release?: string | null }>;
  code?: string;
  /** One ZIP of CSV files with every table, chart's data and number (reproduce.py bundle); meta.download has its url. */
  download?: { label: string; file: string; files: number; bytes: number } | null;
}
export interface Source {
  id: string; kind: 'paper' | 'speech' | 'policy-note' | 'report' | 'dataset' | 'web';
  title: string; titleTranslated?: Partial<Record<Lang, string>>; authors?: string | null;
  institution?: string | null; series?: string | null; number?: string | null; date?: string | null;
  url?: string | null; pdfUrl?: string | null; doi?: string | null;
  quote?: { text: string; lang?: string; locator?: string | null } | null;
  dataset?: { provider?: string; key?: string; unit?: string; frequency?: string; lastObservation?: string; retrieved?: string; attribution?: string;
    /** How to find the series on the provider's site (pipeline/artools/locate.py). */
    locate?: Txt | null } | null;
  cite?: Txt; usedFor?: Txt; citedIn?: string[];
}
export interface Related { title: string; institution?: string; date?: string; url: string; why?: Txt }
export interface Article {
  slug: string; meta: Meta; editions: Partial<Record<Lang, Edition>>;
  /** The glossary terms the article uses, in reading order, with its context (derived by the index). */
  terms: ArticleTerm[];
  /** cover.svg, inlined by the index: the markup inside <svg>, colours as palette classes (site.css § Covers). */
  cover?: { viewBox: string; svg: string; alt?: Txt | null } | null;
  sources: Source[]; related: Related[]; charts: Record<string, ChartSpec>;
}
export interface GlossaryTerm {
  id: string; term: Txt; definition: Txt; topics?: string[]; see?: string[]; approvedBy?: string | null;
  /** Derived by the index: the articles that use the term, and its topics (its own, else its articles'). */
  articles: string[]; topicIds: string[];
}
export interface TopicEntry { id: string; label: Txt; group: string | null; articles: string[]; terms: string[] }
export interface TopicGroup { id: string; label: Txt }

/** An article type and the steps that make it: config/pipelines/<id>.yaml (contracts/content.md § Pipelines). */
export interface PipelineStep {
  id: string; phase: string; label: Txt; detail?: Txt;
  skill?: string; mode?: string; sources?: string; fetch?: string; desk?: string; branches?: Txt[];
  gate?: string; loop?: { owners?: string[]; max?: number }; manual?: boolean;
}
export interface Pipeline {
  id: string; version: string; status: 'live' | 'sample'; name: Txt; tagline: Txt;
  shape?: { words?: Txt; figures?: string; gates?: number };
  phases: Array<{ id: string; label: Txt }>; steps: PipelineStep[];
}

const D = data as unknown as {
  articles: Article[]; glossary: Record<string, GlossaryTerm>; topics: TopicEntry[]; topicGroups?: TopicGroup[]; pipelines: Pipeline[];
  contentDir: string | null; builtAt: string | null; preview?: boolean;
};

export const ARTICLES: Article[] = [...D.articles].sort((a, b) => b.meta.date.localeCompare(a.meta.date));
export const GLOSSARY: Record<string, GlossaryTerm> = D.glossary;
export const TOPICS: TopicEntry[] = D.topics ?? [];
export const TOPIC_GROUPS: TopicGroup[] = D.topicGroups ?? [];
export const PIPELINES: Pipeline[] = D.pipelines ?? [];
export const IS_PREVIEW = Boolean(D.preview);
/** When the content index was built (scripts/build-content-index.mjs), ISO 8601. */
export const BUILT_AT: string | null = D.builtAt ?? null;
export const getArticle = (slug: string) => ARTICLES.find((a) => a.slug === slug);
export const getPipeline = (id: string | undefined) => PIPELINES.find((p) => p.id === id);
export const getTopic = (id: string) => TOPICS.find((x) => x.id === id);
/** The topics that have articles, under their groups in config/topics.yaml's order; a topic outside the registry's
 *  groups goes last, under "More". Topics with no article yet are left out (the home filter and the Topics tree). */
export function topicTree(lang: Lang): Array<{ id: string; label: string; topics: TopicEntry[] }> {
  const used = TOPICS.filter((x) => x.articles.length);
  const known = new Set(TOPIC_GROUPS.map((g) => g.id));
  const out = TOPIC_GROUPS.map((g) => ({ id: g.id, label: tx(g.label, lang), topics: used.filter((x) => x.group === g.id) }));
  out.push({ id: 'more', label: lang === 'ko' ? '기타' : 'More', topics: used.filter((x) => !x.group || !known.has(x.group)) });
  return out.filter((g) => g.topics.length);
}
export const articlesOfType = (id: string) => ARTICLES.filter((a) => (a.meta.type ?? 'explainer') === id);
/** "explainers", "data briefs": the type's name as a plural noun (English); Korean has no plural. */
export const plural = (p: Pipeline, lang: Lang) => (lang === 'en' ? `${tx(p.name, 'en').toLowerCase()}s` : tx(p.name, lang));
/** What an article is built on, for the plate under its cover: data sources as its reference list shows them (one
 *  per indicator, its countries together), research publications (papers, policy notes, reports; not speeches), and
 *  the charts drawn (not the key-number tiles or tables). */
export const coverCounts = (a: Article) => ({
  indicators: a.sources.filter((x) => x.kind === 'dataset').length,
  papers: a.sources.filter((x) => x.kind === 'paper' || x.kind === 'policy-note' || x.kind === 'report').length,
  charts: (a.meta.charts ?? []).filter((id) => a.charts[id] && !['stat-tiles', 'table'].includes(a.charts[id].form)).length,
});
export const editionsOf = (a: Article): Lang[] => (a.meta.editions?.length ? a.meta.editions : (Object.keys(a.editions) as Lang[]));
export function editionOf(a: Article, lang: Lang): { ed: Edition; lang: Lang; fallback: boolean } {
  const ed = a.editions[lang];
  if (ed) return { ed, lang, fallback: false };
  const other = editionsOf(a)[0] ?? 'en';
  return { ed: a.editions[other] as Edition, lang: other, fallback: true };
}
