import fs from 'node:fs';
import path from 'node:path';
import type { ChartSpec } from '@articles/charts';

// A video run's slides for one edition, resolved by `artools video slides` (pipeline/artools/video/slides.py):
// the storyboard's templates and builds, the script's words with every fact token already rendered, and the
// article's chart specs. The studio only lays them out.

const DATA = process.env.ARTICLES_DATA ?? '/data/articles';

export interface Fields { kicker?: string; headline?: string; text?: string; label?: string; items?: string[]; source?: string;
  values?: string[] }           // flow: a value under each node, aligned with items
export interface Fact { id: string; written: string; period?: string | null; label?: string | null }
export interface Build { step: number; highlight?: string; show?: string; annotate?: Fact }
export interface SlideData {
  id: string;
  template: 'question' | 'answer' | 'roadmap' | 'number' | 'compare' | 'figure' | 'findings' | 'term' | 'quote' | 'read' | 'end'
    | 'chapter' | 'thumb'       // the podcast video's part titles and YouTube thumbnail
    | 'flow' | 'story';         // the podcast video's mechanism chain and the story so far
  part: string;
  road: number | null;          // the part's number in the roadmap (1-3), null outside the parts
  steps: number;
  fields: Fields;
  facts: Fact[];
  chart: ChartSpec | null;
  builds: Build[];
}
/** The podcast video's story line: each part's short label (the rail at the top) and what it found. */
export interface StoryPart { id: string; label: string; takeaway?: string; question?: string }
export interface Deck { run: string; lang: 'en' | 'ko'; slug: string; parts: number; slides: SlideData[];
  motion?: boolean;             // the podcast video: slides animate in (studio.css § motion), the rail tracks the story
  story?: StoryPart[] }

export function loadDeck(run: string, lang: string): Deck | null {
  if (!/^\d{8}-[a-z0-9-]+$/.test(run) || (lang !== 'en' && lang !== 'ko')) return null;
  const p = path.join(DATA, 'runs', run, 'slides', `${lang}.resolved.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf8')) as Deck;
}

/** The chart as it stands at a build step: series shown later are hidden, the latest highlight applies, every
 *  annotation so far is drawn. */
export function chartAt(spec: ChartSpec, builds: Build[], step: number): ChartSpec {
  const s: ChartSpec = structuredClone(spec);
  const later = new Set(builds.filter((b) => b.step > step && b.show).map((b) => b.show as string));
  const done = builds.filter((b) => b.step <= step);
  if (s.series) s.series = s.series.filter((x) => !later.has(x.id));
  if (s.categories) s.categories = s.categories.filter((x) => !later.has(x.id));
  if (s.rows) s.rows = s.rows.filter((x) => !later.has(x.id));
  const hl = [...done].reverse().find((b) => b.highlight)?.highlight;
  // a period (2011-11) or a range (2010-01/2012-12) is drawn as a band; anything else names a series or a category
  if (hl && /^\d{4}(-\d{2})?(\/\d{4}(-\d{2})?)?$/.test(hl)) {
    const [from, to = from] = hl.split('/');
    s.bands = [...(s.bands ?? []).filter((b) => !(b.from === from && b.to === to)), { from, to }];
  } else if (hl) {
    if (s.series) s.series = s.series.map((x) => ({ ...x, color: x.id === hl ? 'focus' : 'context' }));
    if (s.categories) s.categories = s.categories.map((x) => ({ ...x, highlight: x.id === hl }));
    if (s.rows) s.rows = s.rows.map((x) => ({ ...x, highlight: x.id === hl }));
  }
  const notes = done.map((b) => b.annotate).filter((f): f is Fact => Boolean(f?.period));
  if (notes.length) s.annotations = [...(s.annotations ?? []), ...notes.map((f) => ({ x: f.period as string, label: f.written }))];
  return s;
}
