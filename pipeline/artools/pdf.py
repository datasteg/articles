"""The PDF edition: each edition of an article printed by Chromium from the site's print page (/print/<lang>/<slug>,
app/print.css), so the PDF has the site's own fonts, charts and colours (contracts/content.md § PDF).

- `proof(run)`, for the make-pdf stage: prints the run's preview into <run>/pdf/<lang>.pdf, with page images to look
  at, and attaches the proofs to the preview site's download button.
- `publish(slugs)`, for `artools ship` and reprints: prints published articles from content/ into
  content/articles/<slug>/pdf/<lang>.pdf and records them in meta.json → pdf.
- `check(run)`: the proof's mechanical checks (validate make-pdf, `artools check pdf`).

Before printing, a layout pass does what LaTeX does with floats: when a figure or table doesn't fit at the bottom of a
page and leaves a large gap, it floats down past up to five of the paragraphs after it (and a heading between them),
so they fill the gap while the figure stays at the top of the next page. Printing goes through the shared preview site, under its lock; `publish` points the site at
content/ while it prints and back at .preview/ after."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

from .paths import CACHE, CONTENT, PREVIEW, read_json, run_dir, write_json
from .render import PORT, reindex, serve, slug_of
from .runlib import flock_file

MAX_PAGES = 40
MAX_MB = 20
MIN_GAP_MM = 45     # a page that ends this much early, because the next figure didn't fit, gets the layout pass
MAX_MOVE = 5        # paragraphs a figure may float past, at most

READY_JS = "() => [...document.querySelectorAll('article.pf .gl-chart')].every(e => e.dataset.ready === '1')"

# Paginate the article in columns as tall as a printed page (Chromium breaks columns as it breaks pages: same width,
# same break rules), then move paragraphs above figures that left a gap, checking each move against the real layout.
LAYOUT_JS = """({ maxMove, minGapMm }) => {
  const doc = document.querySelector('article.pf');
  const probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;visibility:hidden;height:var(--pf-page-height)';
  doc.appendChild(probe);
  const pageH = probe.getBoundingClientRect().height;
  probe.remove();
  const mm = 96 / 25.4, width = doc.getBoundingClientRect().width, gap = 64;
  const saved = doc.getAttribute('style');
  doc.style.cssText = (saved || '') + `;height:${pageH}px;column-width:${width}px;column-gap:${gap}px;column-fill:auto;`;
  const box = () => doc.getBoundingClientRect();
  const at = (r) => { const b = box(); return { page: Math.round((r.left - b.left) / (width + gap)), top: r.top - b.top, bottom: r.bottom - b.top }; };
  const rects = (el) => [...el.getClientRects()].filter((r) => r.height > 0);
  const flow = '.pf-mast, .pf-head, .pf-keynums, .pf-info, .pf-findings li, .pf-question, .pf-h2, .pf-p, .pf-list, .pf-quote, .pf-fig, .pf-tableblock, .pf-insight';
  const bottomOf = (page, before) => {
    let y = 0;
    for (const el of doc.querySelectorAll(flow)) {
      if (el === before) break;
      for (const r of rects(el)) { const w = at(r); if (w.page === page) y = Math.max(y, w.bottom); }
    }
    return y;
  };
  const refersBack = /\\b(above|previous (chart|figure|table))\\b|위(의)?\\s?(그림|차트|표)|앞(의)?\\s?(그림|차트|표)/i;
  // the article's flow after the front matter: a figure may float past paragraphs, lists, quotes, headings and (the
  // last figure) the editor's read, never past another figure or a table, never to just under a heading, and never
  // past text that points back at it
  const flowOf = () => [...doc.querySelectorAll('.pf-main .pf-h2, .pf-main .pf-p, .pf-main .pf-list, .pf-main .pf-quote, .pf-main .pf-fig, .pf-main .pf-tableblock, .pf-main .pf-insight')];
  const moves = [], gaps = [];
  for (const k of doc.querySelectorAll('.pf-main .pf-fig, .pf-main .pf-tableblock')) {
    const r = rects(k)[0];
    if (!r) continue;
    const w = at(r);
    if (w.page === 0 || w.top > 2 * mm) continue;
    const before = pageH - bottomOf(w.page - 1, k);
    if (before < minGapMm * mm) continue;
    const home = [k.parentNode, k.nextSibling];
    const seq = flowOf();
    // keep the furthest place that still leaves the figure whole at the top of its page and makes the gap smaller
    let best = null, bestGap = before, paras = 0, passed = 0;
    for (let j = seq.indexOf(k) + 1; j < seq.length && paras < maxMove; j++) {
      const e = seq[j];
      if (!e.matches('.pf-h2, .pf-p, .pf-list, .pf-quote, .pf-insight') || (!e.matches('.pf-h2') && refersBack.test(e.textContent))) break;
      e.after(k);
      if (e.matches('.pf-h2')) continue;
      paras++;
      const now = rects(k);
      if (!now.length || at(now[0]).page !== w.page || now.length > 1) break;
      const g = pageH - bottomOf(w.page - 1, k);
      if (g < bestGap - mm) { best = e; bestGap = g; passed = paras; }
    }
    if (best) best.after(k); else home[0].insertBefore(k, home[1]);
    const after = pageH - bottomOf(w.page - 1, k);
    const label = k.querySelector('.pf-fig__num')?.textContent || k.querySelector('caption')?.textContent || k.id;
    if (passed) moves.push({ what: label, page: w.page + 1, paragraphs: passed, gapMm: [Math.round(before / mm), Math.round(after / mm)] });
    if (after >= minGapMm * mm) gaps.push({ page: w.page, gapMm: Math.round(after / mm), next: label });
  }
  if (saved === null) doc.removeAttribute('style'); else doc.setAttribute('style', saved);
  return { pageHeightMm: Math.round(pageH / mm), moves, gaps };
}"""

# What would print wrong: things wider than the column, charts not drawn or drawing outside their box
ISSUES_JS = """() => {
  const doc = document.querySelector('article.pf');
  if (!doc) return ['the page has no article.pf: is /print/<lang>/<slug> there?'];
  const out = [];
  const name = (el) => el.closest('figure')?.querySelector('.pf-fig__num')?.textContent || el.closest('[id]')?.id || el.className;
  const right = doc.getBoundingClientRect().right + 1;
  for (const el of doc.querySelectorAll('.pf-fig, .pf-tableblock, .pf-table, .pf-refs li, .pf-info dd, .pf-cite, .pf-steps, pre')) {
    if (el.scrollWidth > el.clientWidth + 2 || el.getBoundingClientRect().right > right) out.push(`${name(el)}: wider than the column`);
  }
  for (const c of doc.querySelectorAll('.gl-chart')) if (c.dataset.ready !== '1') out.push(`${name(c)}: the chart was not drawn`);
  for (const svg of doc.querySelectorAll('.gl-chart svg')) {
    const b = svg.getBBox(), w = svg.width.baseVal.value;
    if (b.x < -3 || b.x + b.width > w + 3) out.push(`${name(svg)}: chart labels run outside the plot`);
  }
  return [...new Set(out)];
}"""


def _pages(pdf: Path) -> int:
    try:
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        return int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    except (OSError, subprocess.CalledProcessError, AttributeError):
        return len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes()))


def _unembedded(pdf: Path) -> list[str] | None:
    """Fonts the PDF uses without embedding them (pdffonts); None when pdffonts isn't installed."""
    try:
        lines = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return None
    if len(lines) < 2:
        return []
    cols = [m.span() for m in re.finditer(r"-+", lines[1])]   # the header's dashes give each column's span
    emb = next((i for i, (a, b) in enumerate(cols) if lines[0][a:b].strip() == "emb"), 3)
    return [l[:cols[0][1]].strip() for l in lines[2:] if l[cols[emb][0]:cols[emb][1]].strip() != "yes"]


def _print(b, lang: str, slug: str, out: Path) -> dict:
    """One edition to PDF: load the print page as print media, wait for the charts and fonts, run the layout pass,
    print A4 with the page rules from app/print.css, a tagged PDF with bookmarks from the headings."""
    pg = b.new_page(viewport={"width": 1000, "height": 1400})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.emulate_media(media="print", color_scheme="light")
    resp = pg.goto(f"http://127.0.0.1:{PORT}/print/{lang}/{slug}", wait_until="networkidle", timeout=180000)
    if not resp or resp.status != 200:
        pg.close()
        return {"lang": lang, "problems": [f"/print/{lang}/{slug} answered {resp.status if resp else 'nothing'}"]}
    try:
        pg.wait_for_function(READY_JS, timeout=30000)
    except Exception:
        pass   # ISSUES_JS names the charts that were not drawn
    pg.evaluate("document.fonts.ready.then(() => true)")
    pg.wait_for_timeout(300)
    layout = pg.evaluate(LAYOUT_JS, {"maxMove": MAX_MOVE, "minGapMm": MIN_GAP_MM})
    problems = pg.evaluate(ISSUES_JS) + [f"script error: {e[:200]}" for e in errors]
    out.parent.mkdir(parents=True, exist_ok=True)
    pg.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True, outline=True, tagged=True)
    pg.close()
    unemb = _unembedded(out)
    return {"lang": lang, "file": out.name, "pages": _pages(out), "bytes": out.stat().st_size, "moves": layout["moves"],
            "gaps": layout["gaps"], "problems": problems + [f"font not embedded: {f}" for f in unemb or []],
            "fonts_checked": unemb is not None}


def _images(pdf: Path, out_dir: Path, lang: str) -> list[str]:
    """Each page as a PNG (60 dpi, enough to judge the layout) and a contact sheet of them all, to look at."""
    for old in out_dir.glob(f"{lang}-*.png"):
        old.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["pdftoppm", "-r", "60", "-png", str(pdf), str(out_dir / lang)], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    pages = sorted(out_dir.glob(f"{lang}-*.png"))
    if pages and shutil.which("montage"):
        subprocess.run(["montage", *map(str, pages), "-tile", "5x", "-geometry", "300x424+8+8", "-background", "#9aa7ad",
                        str(out_dir / f"{lang}-sheet.png")], capture_output=True)
    return [str(p) for p in sorted(out_dir.glob(f"{lang}-*.png"))]


def source_hash(article: Path, lang: str) -> str:
    """What the edition's PDF is printed from: the edition, its sources and its charts (scripts/check-content.mjs
    compares it, so a corrected article whose PDF wasn't printed again fails the production build)."""
    h = hashlib.sha256()
    for f in [article / f"{lang}.json", article / "sources.json", *sorted((article / "charts").glob("*.json"))]:
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _record(r: dict, made: str, article: Path) -> dict:
    return {"file": f"pdf/{r['lang']}.pdf", "pages": r["pages"], "bytes": r["bytes"], "made": made,
            "source": source_hash(article, r["lang"])}


def _attach(article: Path, recs: dict) -> None:
    meta = read_json(article / "meta.json", {}) or {}
    meta["pdf"] = recs or None
    write_json(article / "meta.json", meta)


def proof(run_id: str) -> dict:
    """The make-pdf stage's proof: every edition of the run's preview printed into <run>/pdf/, page images in
    <run>/pdf/render/, a record in <run>/pdf/proof.json, and the proofs on the preview site's download button."""
    from playwright.sync_api import sync_playwright
    from .content import preview
    run = run_dir(run_id)
    slug = slug_of(run)
    out_dir = run / "pdf"
    made = dt.date.today().isoformat()
    eds = {}
    with flock_file(CACHE / "preview-server.lock"):
        built = preview(run_id, slug)
        serve()
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for lang in built["editions"]:
                eds[lang] = _print(b, lang, slug, out_dir / f"{lang}.pdf")
            b.close()
        dest = PREVIEW / "articles" / slug
        (dest / "pdf").mkdir(parents=True, exist_ok=True)
        for lang, r in eds.items():
            if r.get("file"):
                shutil.copyfile(out_dir / r["file"], dest / "pdf" / r["file"])
        _attach(dest, {lang: _record(r, made, dest) for lang, r in eds.items() if r.get("file")})
        reindex()
    for lang, r in eds.items():
        if r.get("file"):
            r["images"] = _images(out_dir / r["file"], out_dir / "render", lang)
    res = {"slug": slug, "made": made, "editions": eds}
    write_json(out_dir / "proof.json", res)
    return {**res, "check": check(run)}


def publish(slugs: list[str] | None = None) -> dict:
    """Print published articles (all of them without `slugs`) from content/ into content/articles/<slug>/pdf/, and
    record each edition in meta.json → pdf. Raises RuntimeError on a blocking problem, leaving that article's files.
    The caller holds the publish lock (artools ship, or `artools pdf`)."""
    from playwright.sync_api import sync_playwright
    adir = CONTENT / "articles"
    slugs = slugs or sorted(p.name for p in adir.iterdir() if (p / "meta.json").is_file())
    made = dt.date.today().isoformat()
    done, failed = {}, {}
    with flock_file(CACHE / "preview-server.lock"):
        serve(CONTENT)
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                for slug in slugs:
                    a = adir / slug
                    meta = read_json(a / "meta.json")
                    if meta is None:
                        failed[slug] = ["no such article in content/"]
                        continue
                    eds = meta.get("editions") or [lang for lang in ("en", "ko") if (a / f"{lang}.json").is_file()]
                    res = {lang: _print(b, lang, slug, a / "pdf" / f"{lang}.pdf") for lang in eds}
                    probs = [f"{lang}: {p}" for lang, r in res.items() for p in r["problems"]]
                    if probs:
                        failed[slug] = probs
                        continue
                    _attach(a, {lang: _record(r, made, a) for lang, r in res.items()})
                    done[slug] = {lang: {k: r[k] for k in ("pages", "bytes", "moves", "gaps")} for lang, r in res.items()}
                b.close()
        finally:
            reindex()   # the preview site serves .preview/ again
    if failed:
        raise RuntimeError(f"PDF problems: {failed}")
    return {"printed": done}


def check(run: Path) -> dict:
    """The proof: one PDF per edition, newer than the draft and the charts, 1 to 40 pages, under 20 MB, fonts
    embedded, nothing wider than the column, every chart drawn. Pages that end early are advisory."""
    blocking, advisory = [], []
    proof_rec = read_json(run / "pdf" / "proof.json", None)
    eds = [lang for lang in ("en", "ko") if (run / "draft" / f"{lang}.json").is_file()]
    if not proof_rec:
        return {"blocking": [f"no proof yet: artools render pdf {run.name}"], "advisory": [], "pages": {}}
    inputs = [run / "draft" / f"{lang}.json" for lang in eds] + [p for p in (run / "charts").glob("*.json") if not p.name.endswith(".log.json")]
    newest = max((p.stat().st_mtime for p in inputs if p.is_file()), default=0)
    pages = {}
    for lang in eds:
        r = (proof_rec.get("editions") or {}).get(lang) or {}
        f = run / "pdf" / f"{lang}.pdf"
        if not f.is_file() or not r.get("file"):
            blocking.append(f"{lang}: no PDF")
            continue
        if f.stat().st_mtime < newest:
            blocking.append(f"{lang}: the PDF is older than the draft or the charts; print it again")
        pages[lang] = r.get("pages", 0)
        if not 1 <= pages[lang] <= MAX_PAGES:
            blocking.append(f"{lang}: {pages[lang]} pages (1 to {MAX_PAGES})")
        if r.get("bytes", 0) > MAX_MB * 1e6:
            blocking.append(f"{lang}: {r['bytes'] / 1e6:.1f} MB (at most {MAX_MB} MB)")
        blocking += [f"{lang}: {p}" for p in r.get("problems", [])]
        if not r.get("fonts_checked"):
            advisory.append(f"{lang}: fonts not checked (pdffonts is not installed)")
        advisory += [f"{lang}: page {g['page']} ends {g['gapMm']} mm early: {g['next']} did not fit under it" for g in r.get("gaps", [])]
    return {"blocking": blocking, "advisory": advisory, "pages": pages}
