// Content index for the web app: reads CONTENT_DIR (default content/, relative to this app folder), the article
// types in config/pipelines/*.yaml and the topic registry config/topics.yaml, writes apps/web/generated/content.json, copies each chart's CSV to
// apps/web/public/data/<slug>/ and each PDF edition to apps/web/public/pdf/<slug>-<lang>.pdf. Format: contracts/content.md. Run by `pnpm dev` and `pnpm build`;
// `artools preview` sets CONTENT_DIR=.preview.
// Derived here, so the newsroom never has to keep them in step: each article's terms (from its ((id)) marks, in
// reading order, with meta.terms[].context), each term's articles and topics, and each topic's articles and terms.
// Each article's cover (cover.svg, guides/covers.md) is inlined, so its colour classes follow the theme.
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { basename, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse as parseYaml } from 'yaml';

const app = new URL('..', import.meta.url).pathname;
const dir = process.env.CONTENT_DIR ? (isAbsolute(process.env.CONTENT_DIR) ? process.env.CONTENT_DIR : resolve(app, process.env.CONTENT_DIR)) : join(app, 'content');
const out = join(app, 'apps/web/generated/content.json');
const pub = join(app, 'apps/web/public/data');
const pubPdf = join(app, 'apps/web/public/pdf');
const read = (f, fallback) => (existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : fallback);

/** Every ((id)) or ((id|text)) mark in a value, depth first in key order (an edition's keys are in reading order). */
export function termMarks(v, found = []) {
  if (typeof v === 'string') for (const m of v.matchAll(/\(\(([^)|]+)(?:\|[^)]*)?\)\)/g)) found.push(m[1].trim());
  else if (Array.isArray(v)) v.forEach((x) => termMarks(x, found));
  else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) if (k !== 'citations') termMarks(x, found);
  return found;
}

/** The topic registry, config/topics.yaml: its order and labels win over the labels in an article's meta. */
export function loadTopics(root = app) {
  const f = join(root, 'config/topics.yaml');
  return existsSync(f) ? (parseYaml(readFileSync(f, 'utf8'))?.topics ?? []) : [];
}

/** The registry's groups (Markets, Policy …), in order: the home page's topic filter and the Topics tree list topics under them. */
export function loadTopicGroups(root = app) {
  const f = join(root, 'config/topics.yaml');
  return existsSync(f) ? (parseYaml(readFileSync(f, 'utf8'))?.groups ?? []) : [];
}

// What a cover may contain (pipeline/artools/cover.py is the full check; this is the site's own guard before inlining)
const COVER_TAGS = new Set(['g', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path']);
const COVER_ATTRS = new Set(['x', 'y', 'width', 'height', 'rx', 'ry', 'cx', 'cy', 'r', 'x1', 'y1', 'x2', 'y2', 'points', 'd',
  'opacity', 'fill-opacity', 'stroke-opacity', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray',
  'stroke-miterlimit', 'fill-rule', 'transform', 'class', 'fill', 'stroke']);

/** An article's cover: {cover: {viewBox, svg (the markup inside <svg>), alt} | null, problems}. */
export function readCover(a, meta) {
  if (!meta.cover) return { cover: null, problems: [] };
  const f = join(a, meta.cover.file ?? 'cover.svg');
  if (!existsSync(f)) return { cover: null, problems: [`meta.cover names ${meta.cover.file}, which is missing`] };
  const text = readFileSync(f, 'utf8').replace(/<!--[\s\S]*?-->/g, '').replace(/^\s*<\?xml[^>]*\?>/, '');
  const m = text.match(/^\s*<svg\b([^>]*)>([\s\S]*)<\/svg>\s*$/);
  if (!m) return { cover: null, problems: ['cover.svg is not one <svg> element'] };
  const problems = [];
  const viewBox = m[1].match(/\bviewBox="([^"]+)"/)?.[1];
  if (viewBox !== '0 0 480 320') problems.push(`cover.svg: viewBox is "${viewBox}", not "0 0 480 320"`);
  const body = m[2].trim();
  for (const t of body.matchAll(/<\/?([a-zA-Z][\w:.-]*)/g)) if (!COVER_TAGS.has(t[1])) problems.push(`cover.svg: <${t[1]}> is not allowed`);
  for (const t of body.matchAll(/\s([a-zA-Z_:][\w:.-]*)\s*=/g)) if (!COVER_ATTRS.has(t[1])) problems.push(`cover.svg: attribute ${t[1]} is not allowed`);
  if (/<!|<\?|&|url\s*\(|javascript:/i.test(body)) problems.push('cover.svg: declarations, entities and url() are not allowed');
  if (/\b(fill|stroke)\s*=\s*"(?!none")/.test(body)) problems.push('cover.svg: colours are classes; fill and stroke may only be "none"');
  return { cover: problems.length ? null : { viewBox, svg: body, alt: meta.cover.alt ?? null }, problems };
}

/** Article types: config/pipelines/*.yaml, live ones first. */
export function loadPipelines(root = app) {
  const pdir = join(root, 'config/pipelines');
  const list = (existsSync(pdir) ? readdirSync(pdir).filter((f) => /\.ya?ml$/.test(f)).sort() : [])
    .map((f) => ({ file: f, ...parseYaml(readFileSync(join(pdir, f), 'utf8')) }));
  return list.sort((a, b) => (a.status === 'live' ? 0 : 1) - (b.status === 'live' ? 0 : 1));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {   // run, not imported by check-content
  rmSync(pub, { recursive: true, force: true });
  rmSync(pubPdf, { recursive: true, force: true });
  const articles = [];
  const adir = join(dir, 'articles');
  for (const slug of existsSync(adir) ? readdirSync(adir).sort() : []) {
    const a = join(adir, slug);
    if (!existsSync(join(a, 'meta.json'))) continue;
    const meta = read(join(a, 'meta.json'));
    const editions = {};
    for (const lang of ['en', 'ko']) { const e = read(join(a, `${lang}.json`), null); if (e) editions[lang] = e; }
    const charts = {};
    const cdir = join(a, 'charts');
    for (const f of existsSync(cdir) ? readdirSync(cdir).filter((x) => x.endsWith('.json')) : []) {
      const c = read(join(cdir, f));
      if (c.csv && existsSync(join(a, c.csv))) {
        mkdirSync(join(pub, slug), { recursive: true });
        cpSync(join(a, c.csv), join(pub, slug, basename(c.csv)));
        c.csvUrl = `/data/${slug}/${basename(c.csv)}`;
      }
      charts[c.id ?? f.replace(/\.json$/, '')] = c;
    }
    const context = new Map((meta.terms ?? []).map((x) => [x.id, x.context ?? null]));
    const ids = [...new Set([...termMarks(editions.en ?? {}), ...termMarks(editions.ko ?? {}), ...context.keys()])];
    const terms = ids.map((id) => ({ id, context: context.get(id) ?? null }));
    // the PDF edition (meta.pdf, written by `artools pdf`): served as /pdf/<slug>-<lang>.pdf; a missing file is left out
    for (const [lang, p] of Object.entries(meta.pdf ?? {})) {
      if (!p?.file || !existsSync(join(a, p.file))) { delete meta.pdf[lang]; continue; }
      mkdirSync(pubPdf, { recursive: true });
      cpSync(join(a, p.file), join(pubPdf, `${slug}-${lang}.pdf`));
      p.url = `/pdf/${slug}-${lang}.pdf`;
    }
    // a data note's data download (meta.download, written by `artools` from the desk's bundle): /data/<slug>/datasteg-<slug>-data.zip
    if (meta.download?.file && existsSync(join(a, meta.download.file))) {
      mkdirSync(join(pub, slug), { recursive: true });
      cpSync(join(a, meta.download.file), join(pub, slug, `datasteg-${slug}-data.zip`));
      meta.download.url = `/data/${slug}/datasteg-${slug}-data.zip`;
    } else if (meta.download) delete meta.download;
    const { cover, problems } = readCover(a, meta);
    for (const x of problems) console.warn(`warning: articles/${slug}: ${x}; the cover is left out`);
    articles.push({ slug, meta, editions, terms, cover, sources: read(join(a, 'sources.json'), []), related: read(join(a, 'related.json'), []), charts });
  }

  const glossary = {};
  const gdir = join(dir, 'glossary');
  for (const f of existsSync(gdir) ? readdirSync(gdir).filter((x) => x.endsWith('.json')) : []) {
    const g = read(join(gdir, f));
    glossary[g.id ?? f.replace(/\.json$/, '')] = g;
  }
  // topics: the registry's, in its order, then any an article names that the registry doesn't
  const topics = new Map(loadTopics().map((t) => [t.id, { id: t.id, label: t.label, group: t.group ?? null, articles: [], terms: [] }]));
  for (const a of articles) for (const t of a.meta.topics ?? []) if (!topics.has(t.id)) topics.set(t.id, { id: t.id, label: t.label, group: null, articles: [], terms: [] });
  for (const a of articles) for (const t of a.meta.topics ?? []) t.label = topics.get(t.id).label;
  for (const a of [...articles].sort((x, y) => y.meta.date.localeCompare(x.meta.date))) for (const t of a.meta.topics ?? []) topics.get(t.id).articles.push(a.slug);
  for (const g of Object.values(glossary)) {
    const users = articles.filter((a) => a.terms.some((x) => x.id === g.id));
    g.articles = users.map((a) => a.slug);
    g.topicIds = g.topics?.length ? g.topics : [...new Set(users.flatMap((a) => (a.meta.topics ?? []).map((t) => t.id)))];
    for (const id of g.topicIds) topics.get(id)?.terms.push(g.id);
  }

  const pipelines = loadPipelines().map(({ file, ...p }) => p);
  mkdirSync(join(app, 'apps/web/generated'), { recursive: true });
  const used = [...topics.values()].filter((t) => t.articles.length || t.terms.length);   // only topics in use
  const topicGroups = loadTopicGroups().map((g) => ({ id: g.id, label: g.label }));
  writeFileSync(out, JSON.stringify({ articles, glossary, topics: used, topicGroups, pipelines, contentDir: dir, builtAt: new Date().toISOString(), preview: process.env.PREVIEW === '1' }));
  console.log(`content index: ${articles.length} article(s), ${Object.keys(glossary).length} glossary term(s), ${used.length} topic(s) in use, ${pipelines.length} article type(s) from ${dir}`);
}
