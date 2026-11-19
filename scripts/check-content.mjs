// Content checks run by `pnpm build` (and so by every Docker build), against contracts/content.md:
// every [[S#]] resolves, every ((term)) resolves (warning), every figure's chart exists and has its axes
// labels, alt text and source line in each edition; the editions agree on key numbers and on the digits in
// their findings. A production build (PREVIEW unset) fails on any article the editor hasn't approved.
// Article types (config/pipelines/*.yaml): each one is well formed, and each article's meta.type has one;
// glossary links (meta.terms, a term's `see`) resolve (warnings); a cover is safe to inline (guides/covers.md).
// Topics: every topic in config/topics.yaml names a group the file defines. Citation: an approved article carries
// meta.citation (stamped by `artools publish`) with each edition's title and URL. PDF: an approved article has a PDF
// of each edition (meta.pdf, printed by `artools pdf`), printed from the edition as it now is.
import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';
import { loadPipelines, loadTopicGroups, loadTopics, readCover } from './build-content-index.mjs';

const app = new URL('..', import.meta.url).pathname;
const dir = process.env.CONTENT_DIR ? (isAbsolute(process.env.CONTENT_DIR) ? process.env.CONTENT_DIR : resolve(app, process.env.CONTENT_DIR)) : join(app, 'content');
const preview = process.env.PREVIEW === '1';
const errors = [], warnings = [];
const read = (f) => JSON.parse(readFileSync(f, 'utf8'));
const tx = (v, lang) => (v == null ? '' : typeof v === 'string' ? v : v[lang] ?? '');
// Numbers that must match across editions: dates are written differently ("September 2026" / "2026년 9월"),
// so day and month numbers are left out; years and every other number stay.
const MONTH = '(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*';
const digits = (s) => (String(s)
  .replace(/\[\[[^\]]*\]\]/g, '')
  .replace(/\d{1,2}\s*(?:월|일)/g, '')
  .replace(new RegExp(`\\b\\d{1,2}\\s+(?=${MONTH}\\b)`, 'g'), '')
  .match(/\d+(?:[.,]\d+)*/g) ?? []).map((x) => x.replace(/,/g, '')).sort().join(' ');

const glossary = new Set();
const terms = [];
if (existsSync(join(dir, 'glossary'))) for (const f of readdirSync(join(dir, 'glossary'))) if (f.endsWith('.json')) { const g = read(join(dir, 'glossary', f)); glossary.add(g.id ?? f.replace(/\.json$/, '')); terms.push(g); }
for (const g of terms) for (const id of g.see ?? []) if (!glossary.has(id)) warnings.push(`glossary/${g.id}: see "${id}" has no glossary/${id}.json`);

const registry = new Set(loadTopics(app).map((t) => t.id));
const groups = new Set(loadTopicGroups(app).map((g) => g.id));
for (const g of loadTopicGroups(app)) if (!g.label?.en || !g.label?.ko) errors.push(`config/topics.yaml: group ${g.id} needs an en and ko label`);
for (const t of loadTopics(app)) if (!groups.has(t.group)) errors.push(`config/topics.yaml: topic ${t.id} names group "${t.group}", which the file doesn't define`);
for (const g of terms) for (const id of g.topics ?? []) if (registry.size && !registry.has(id)) warnings.push(`glossary/${g.id}: topic "${id}" is not in config/topics.yaml`);

// article types: unique step ids, known phases, labels in both languages, gates named
const both = (v) => v && typeof v === 'object' && v.en && v.ko;
const types = new Set();
for (const p of loadPipelines(app)) {
  const where = `config/pipelines/${p.file}`;
  if (!p.id || `${p.id}.yaml` !== p.file) errors.push(`${where}: id "${p.id}" does not match the file name`);
  types.add(p.id);
  if (!['live', 'sample'].includes(p.status)) errors.push(`${where}: status must be live or sample`);
  if (!both(p.name) || !both(p.tagline)) errors.push(`${where}: name and tagline need en and ko`);
  const phases = new Set((p.phases ?? []).map((x) => x.id));
  for (const ph of p.phases ?? []) if (!both(ph.label)) errors.push(`${where}: phase ${ph.id} needs an en and ko label`);
  const seen = new Set();
  for (const st of p.steps ?? []) {
    if (seen.has(st.id)) errors.push(`${where}: step id ${st.id} is used twice`);
    seen.add(st.id);
    if (!phases.has(st.phase)) errors.push(`${where}: step ${st.id} is in unknown phase "${st.phase}"`);
    if (!both(st.label)) errors.push(`${where}: step ${st.id} needs an en and ko label`);
    if (st.detail && !both(st.detail)) errors.push(`${where}: step ${st.id} detail needs en and ko`);
    for (const b of st.branches ?? []) if (!both(b)) errors.push(`${where}: step ${st.id} has a branch without en and ko`);
    if (!st.gate && !st.skill && !st.sources && !st.fetch && !st.desk) errors.push(`${where}: step ${st.id} names no skill, gate, sources, fetch or desk step`);
  }
  if (!(p.steps ?? []).length) errors.push(`${where}: no steps`);
}

/** What a PDF edition is printed from (pipeline/artools/pdf.py source_hash): the edition, its sources and its charts. */
function pdfSource(a, lang) {
  const h = createHash('sha256');
  const cdir = join(a, 'charts');
  const charts = existsSync(cdir) ? readdirSync(cdir).filter((x) => x.endsWith('.json')).sort().map((x) => join(cdir, x)) : [];
  for (const f of [join(a, `${lang}.json`), join(a, 'sources.json'), ...charts]) if (existsSync(f)) h.update(readFileSync(f));
  return h.digest('hex').slice(0, 16);
}

const adir = join(dir, 'articles');
for (const slug of existsSync(adir) ? readdirSync(adir) : []) {
  const a = join(adir, slug);
  const where = `articles/${slug}`;
  if (!existsSync(join(a, 'meta.json'))) { errors.push(`${where}: missing meta.json`); continue; }
  const meta = read(join(a, 'meta.json'));
  if (meta.slug !== slug) errors.push(`${where}: meta.slug is "${meta.slug}"`);
  if (!types.has(meta.type ?? 'explainer')) (preview ? warnings : errors).push(`${where}: type "${meta.type}" has no config/pipelines/${meta.type}.yaml`);
  for (const t of meta.topics ?? []) if (registry.size && !registry.has(t.id)) warnings.push(`${where}: topic "${t.id}" is not in config/topics.yaml (its own label is used)`);
  for (const x of meta.terms ?? []) if (!glossary.has(x.id)) warnings.push(`${where}: meta.terms lists ${x.id}, which has no glossary/${x.id}.json`);
  for (const x of readCover(a, meta).problems) errors.push(`${where}: ${x}`);
  if (meta.cover && !tx(meta.cover.alt, 'en')) warnings.push(`${where}: the cover has no alt text`);
  if (!preview && !meta.review?.approved) errors.push(`${where}: not approved by the editor (meta.review.approved is empty); production builds publish approved articles only`);
  const langs = meta.editions?.length ? meta.editions : ['en', 'ko'];
  const plainTitle = (x) => String(x ?? '').replace(/\s*\[\[[^\]]*\]\]/g, '').replace(/\(\(([^)|]+)(?:\|([^)]*))?\)\)/g, (_m, id, text) => text || id).replace(/\*([^*]+)\*/g, '$1').trim();
  const cite = meta.citation;
  const sources = existsSync(join(a, 'sources.json')) ? read(join(a, 'sources.json')) : [];
  const ids = new Set(sources.map((x) => x.id));
  const charts = {};
  for (const id of meta.charts ?? []) {
    const f = join(a, 'charts', `${id}.json`);
    if (!existsSync(f)) { errors.push(`${where}: chart ${id} listed in meta.json has no charts/${id}.json`); continue; }
    charts[id] = read(f);
  }
  const eds = {};
  for (const lang of langs) {
    const f = join(a, `${lang}.json`);
    if (!existsSync(f)) { errors.push(`${where}: missing ${lang}.json (meta.editions lists it)`); continue; }
    eds[lang] = read(f);
  }
  if (!cite) (preview ? warnings : errors).push(`${where}: no meta.citation (artools publish stamps it from config/editorial.yaml)`);
  for (const [lang, e] of Object.entries(eds)) {
    const pdf = meta.pdf?.[lang];
    if (!pdf) (preview ? warnings : errors).push(`${where}/${lang}: no PDF edition (meta.pdf.${lang}): \`artools pdf ${slug}\` prints it`);
    else if (!pdf.file || !existsSync(join(a, pdf.file))) errors.push(`${where}/${lang}: meta.pdf.${lang}.file (${pdf.file}) is missing`);
    else if (!(pdf.pages > 0) || !(pdf.bytes > 0)) errors.push(`${where}/${lang}: meta.pdf.${lang} needs pages and bytes`);
    else if (pdf.source && pdf.source !== pdfSource(a, lang)) (preview ? warnings : errors).push(`${where}/${lang}: the PDF was printed from an earlier version of the edition, its sources or charts: \`artools pdf ${slug}\` prints it again`);
    if (cite) {
      if (!tx(cite.author, lang) || !tx(cite.publisher, lang) || !cite.date) errors.push(`${where}/${lang}: meta.citation needs author, publisher and date`);
      if (tx(cite.title, lang) !== plainTitle(e.title)) errors.push(`${where}/${lang}: meta.citation.title is "${tx(cite.title, lang)}", not the edition's title`);
      if (!tx(cite.url, lang).endsWith(`/${lang}/a/${slug}`)) errors.push(`${where}/${lang}: meta.citation.url "${tx(cite.url, lang)}" doesn't end in /${lang}/a/${slug}`);
    }
    const texts = [e.dek, ...(e.findings ?? []), e.insight?.text ?? ''];
    for (const k of e.keyNumbers ?? []) for (const c of k.cite ?? []) if (!ids.has(c)) errors.push(`${where}/${lang}: key number cites unknown ${c}`);
    for (const sec of e.sections ?? []) for (const b of sec.blocks ?? []) {
      if (b.type === 'p') texts.push(b.text);
      if (b.type === 'list') texts.push(...b.items);
      if (b.type === 'quote' && b.cite && !ids.has(b.cite)) errors.push(`${where}/${lang}: quote cites unknown ${b.cite}`);
      if (b.type === 'table' && b.source && !ids.has(b.source)) errors.push(`${where}/${lang}: table cites unknown ${b.source}`);
      if (b.type === 'figure' && !charts[b.chart]) errors.push(`${where}/${lang}: figure ${b.chart} is not in meta.charts or has no file`);
    }
    for (const t of texts) {
      for (const m of String(t).matchAll(/\[\[([^\]]+)\]\]/g)) for (const id of m[1].split(',').map((x) => x.trim())) if (!ids.has(id)) errors.push(`${where}/${lang}: [[${id}]] has no entry in sources.json`);
      for (const m of String(t).matchAll(/\(\(([^)|]+)(?:\|[^)]*)?\)\)/g)) if (!glossary.has(m[1])) warnings.push(`${where}/${lang}: glossary term ((${m[1]})) has no glossary/${m[1]}.json; shown as plain text`);
    }
    for (const [id, c] of Object.entries(charts)) {
      if (!tx(c.alt, lang)) errors.push(`${where}/${lang}: chart ${id} has no alt text`);
      if (!tx(c.meta?.attribution, lang)) errors.push(`${where}/${lang}: chart ${id} has no source line (meta.attribution)`);
      for (const s of c.meta?.sources ?? []) if (!ids.has(s)) errors.push(`${where}: chart ${id} cites unknown ${s}`);
      const axes = c.form === 'line' || c.form === 'scatter' ? ['x', 'y'] : c.form === 'bars' || c.form === 'dumbbell' ? ['x'] : [];
      for (const ax of axes) if (!tx(c.axes?.[ax]?.label, lang)) errors.push(`${where}/${lang}: chart ${id} has no ${ax}-axis label`);
    }
  }
  if (eds.en && eds.ko) {
    // the numbers of each key number, not its words: "3.78 months" is "3.78개월", "USD 82.6 bn" is "826억 달러",
    // "three months" is "3개월" (19 Nov 2026: an exact match stopped 20261119-desk, whose key number was in months)
    const WORDS = { zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9 };
    const knNums = (v, ko) => {
      let t = String(v);
      if (ko) t = t.replace(/(?:(\d[\d,]*)조\s*)?(\d[\d,.]*)억/g, (_, jo, eok) => String((Number((jo ?? '0').replace(/,/g, '')) * 10000 + Number(eok.replace(/,/g, ''))) / 10))
        .replace(/(\d[\d,.]*)조/g, (_, jo) => String(Number(jo.replace(/,/g, '')) * 1000));
      else t = t.replace(/\b(zero|one|two|three|four|five|six|seven|eight|nine)\b/gi, (w) => String(WORDS[w.toLowerCase()]));
      t = t.replace(/(\d[\d,.]*)\s*tn\b/g, (_, n) => String(Number(n.replace(/,/g, '')) * 1000));      // either edition may write "$1.79tn"
      return (t.match(/[−-]?\d[\d,]*(?:\.\d+)?/g) ?? []).map((x) => String(Number(x.replace(/,/g, '').replace('−', '-')))).join(' ');
    };
    const kn = (e, ko) => (e.keyNumbers ?? []).map((k) => knNums(k.value, ko)).join(' | ');
    if (kn(eds.en, false) !== kn(eds.ko, true)) errors.push(`${where}: key numbers differ: en "${kn(eds.en, false)}" vs ko "${kn(eds.ko, true)}"`);
    const fa = eds.en.findings ?? [], fb = eds.ko.findings ?? [];
    if (fa.length !== fb.length) errors.push(`${where}: findings has ${fa.length} items in English, ${fb.length} in Korean`);
    // dates and counts are written differently by language ("July 2012" / "2012년 7월", "four" / "4개국"), so this is a hint;
    // the pipeline guarantees parity by rendering both editions from the same fact tokens (artools check numbers)
    else fa.forEach((x, i) => { if (digits(x) !== digits(fb[i])) warnings.push(`${where}: findings[${i}] digits differ (check by eye): en "${digits(x)}" vs ko "${digits(fb[i])}"`); });
  }
}
for (const w of warnings) console.warn('warning: ' + w);
if (errors.length) { console.error('Content check failed:\n  ' + errors.join('\n  ')); process.exit(1); }
console.log(`content: ok (${dir}${preview ? ', preview' : ''})`);
