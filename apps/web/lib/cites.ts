import type { ChartSpec } from '@articles/charts';
import type { Article, Edition } from './content';

export interface Place { anchor: string; label: string }

/** Citation numbers in order of first appearance on the page, and where each source is cited
 *  (for the references' back-links). Walks the edition in render order. */
export function citations(a: Article, ed: Edition, labels: { keyNumbers: string; findings: string; insight: string }) {
  const nums = new Map<string, number>();
  const places = new Map<string, Place[]>();
  const known = new Set(a.sources.map((x) => x.id));
  const add = (ids: string[], place: Place) => {
    for (const id of ids) {
      if (!known.has(id)) continue;
      if (!nums.has(id)) nums.set(id, nums.size + 1);
      const list = places.get(id) ?? [];
      if (!list.some((p) => p.anchor === place.anchor)) list.push(place);
      places.set(id, list);
    }
  };
  const inText = (t: string | undefined | null) => [...String(t ?? '').matchAll(/\[\[([^\]]+)\]\]/g)].flatMap((m) => m[1].split(',').map((x) => x.trim()));
  const chartIds = (c?: ChartSpec) => [...(c?.meta?.sources ?? []), ...(c?.tiles ?? []).flatMap((t) => t.cite ?? [])];

  const kn = { anchor: 'key-numbers', label: labels.keyNumbers };
  for (const k of ed.keyNumbers ?? []) add(k.cite ?? [], kn);
  add(inText(ed.dek), kn);
  const fi = { anchor: 'findings', label: labels.findings };
  for (const f of ed.findings ?? []) add(inText(f), fi);
  for (const sec of ed.sections ?? []) {
    const place = { anchor: `sec-${sec.id}`, label: sec.heading };
    for (const b of sec.blocks ?? []) {
      if (b.type === 'p') add(inText(b.text), place);
      else if (b.type === 'list') b.items.forEach((x) => add(inText(x), place));
      else if (b.type === 'quote' && b.cite) add([b.cite], place);
      else if (b.type === 'table' && b.source) add([b.source], place);
      else if (b.type === 'figure') add(chartIds(a.charts[b.chart]), place);
    }
  }
  if (ed.insight?.text) add(inText(ed.insight.text), { anchor: 'insight', label: labels.insight });
  // anything in sources.json never cited still gets a number, after the cited ones
  for (const src of a.sources) if (!nums.has(src.id)) nums.set(src.id, nums.size + 1);
  return { nums, places };
}

/** Figure numbers in order of appearance. */
export function figureNumbers(ed: Edition): Map<string, number> {
  const out = new Map<string, number>();
  for (const sec of ed.sections ?? []) for (const b of sec.blocks ?? []) if (b.type === 'figure' && !out.has(b.chart)) out.set(b.chart, out.size + 1);
  return out;
}
