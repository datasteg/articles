"""`artools video slides`: the storyboard and scripts resolved into slides, rendered by the local studio
(apps/studio, 127.0.0.1:3313) and screenshot at 1920×1080, every build step, plus a contact sheet per edition.

<run>/slides/<lang>.resolved.json   what the studio lays out (tokens rendered, chart specs, builds)
<run>/slides/<lang>/<slide>-<step>.png
<run>/slides/<lang>-sheet.png        the contact sheet
<run>/slides/<lang>/<slide>-<step>.mp4  the podcast video's decks (motion): the step's enter animation, ~1 s at 30 fps,
                                     encoded from frames in a temporary folder; the PNG is its last frame
<run>/slides/render.json             per frame: file, clip, and anything that spills into the caption zone or margins;
                                     rail: where each part's track sits (the assembly fills the current one)"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from ..content import CITE, GLOSS
from ..paths import ARTICLES, CACHE, die, read_json, run_dir, write_json
from ..runlib import flock_file
from . import cfg
from .doctor import ffmpeg
from .script import facts_of
from .speech import render

PORT = int(os.environ.get("ARTICLES_STUDIO_PORT", "3313"))
FIG_WORD = {"en": "Figure", "ko": "그림"}
SOURCE_WORD = {"en": "Source", "ko": "출처"}
FIT_JS = """() => {
  // Scale the chart to the room it has: the full text width, and the height left above the source line and the
  // caption zone. Measured at zoom 1, so every label scales with the plot.
  const c = document.querySelector('.vs-chart'); if (!c) return null;
  c.style.zoom = '1'; c.style.flex = 'none';
  const natW = 680, natH = c.getBoundingClientRect().height;
  const src = document.querySelector('.vs-source');
  const srcH = src ? src.getBoundingClientRect().height + 18 : 0;
  const room = (1080 - 162) - c.getBoundingClientRect().top - srcH - 24;
  const z = Math.max(1, Math.min((1920 - 2 * 96) / natW, room / natH));
  c.style.zoom = String(z);
  return Math.round(z * 100) / 100;
}"""
SPILL_JS = """() => {
  const s = document.querySelector('section.vs'); if (!s) return ['no slide'];
  const W = 1920, H = 1080, side = 96, foot = 162, out = [];
  for (const el of s.querySelectorAll('.vs-in *')) {
    if (el.closest('.is-later')) continue;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    const name = el.className && typeof el.className === 'string' ? el.className.split(' ')[0] : el.tagName.toLowerCase();
    if (r.bottom > H - foot + 2) out.push(`${name} reaches into the caption zone (${Math.round(r.bottom)} px > ${H - foot})`);
    if (r.right > W - side + 2 || r.left < side - 2) out.push(`${name} crosses the side margin`);
  }
  return [...new Set(out)].slice(0, 6);
}"""

FPS = 30
# Motion: pause every animation and report when the last one ends (ms); then step them to each frame's time.
PAUSE_JS = """() => { const as = document.getAnimations(); as.forEach((a) => a.pause());
  return Math.max(0, ...as.map((a) => a.effect.getComputedTiming().endTime || 0)); }"""
SEEK_JS = "(t) => { document.getAnimations().forEach((a) => { a.currentTime = t; }); }"
RAIL_JS = """() => Object.fromEntries([...document.querySelectorAll('.vs-rail [data-part] i')].map((el) => {
  const r = el.getBoundingClientRect();
  return [el.parentElement.dataset.part, [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]]; }))"""


def _plain(t: str) -> str:
    """Inline marks off: citations dropped, glossary marks to their text, emphasis to plain."""
    t = CITE.sub("", t)
    t = GLOSS.sub(lambda m: m.group(0)[2:-2].split("|")[-1], t)
    return t.replace("*", "").strip()


def _figure_numbers(edition: dict) -> dict:
    out = {}
    for sec in edition.get("sections", []):
        for b in sec.get("blocks", []):
            if b.get("type") == "figure" and b.get("chart") not in out:
                out[b["chart"]] = len(out) + 1
    return out


def resolve(run: Path) -> dict:
    sb = read_json(run / "storyboard.json")
    if not sb:
        die("storyboard.json is missing: write-video-script comes first")
    facts = facts_of(run)
    meta = read_json(run / "source" / "meta.json", {}) or {}
    pub = cfg("publish")["youtube"]
    road = {p["id"]: i + 1 for i, p in enumerate(x for x in sb["parts"] if x["kind"] == "part")}
    written = {}
    for lang in ("en", "ko"):
        sc = read_json(run / "script" / f"{lang}.json")
        if not sc:
            die(f"script/{lang}.json is missing")
        ed = read_json(run / "source" / f"{lang}.json", {}) or {}
        fig_n = _figure_numbers(ed)

        def r(t: str) -> str:
            return _plain(render(t, facts, lang))

        def fact(fid: str) -> dict:
            f = facts.get(fid) or {}
            return {"id": fid, "written": render(f"{{{{{fid}}}}}", facts, lang) if f else fid,
                    "period": f.get("period") if isinstance(f.get("period"), str) else None, "label": f.get("label")}

        slides = []
        for s in sb["slides"]:
            raw = (sc.get("slides") or {}).get(s["id"], {})
            fields = {k: ([r(x) for x in v] if isinstance(v, list) else r(v)) for k, v in raw.items()}
            chart = read_json(run / "source" / "charts" / f"{s['chart']}.json") if s.get("chart") else None
            if s["template"] == "figure":
                fields.setdefault("kicker", f"{FIG_WORD[lang]} {fig_n.get(s.get('chart'), '')}".strip())
                if not fields.get("source") and chart:
                    m = chart.get("meta") or {}
                    who = m.get("attribution") or m.get("provider") or ""
                    who = who.get(lang, who.get("en", "")) if isinstance(who, dict) else who
                    if who:
                        fields["source"] = f"{SOURCE_WORD[lang]}: {who}"
            if s["template"] == "read":
                fields.setdefault("kicker", (ed.get("insight") or {}).get("label"))
            if s["template"] == "end":
                fields.setdefault("text", f"articles.datasteg.com/{lang}/a/{sb.get('slug') or meta.get('slug')}")
                fields.setdefault("label", f"{pub['disclaimer'][lang]} {pub['disclosure'][lang]}")
            builds = [{k: (fact(v) if k == "annotate" else v) for k, v in b.items()} for b in s.get("builds", [])]
            slides.append({"id": s["id"], "template": s["template"], "part": s["part"], "road": road.get(s["part"]),
                           "steps": s.get("steps") or 1, "fields": {k: v for k, v in fields.items() if v},
                           "facts": [fact(x) for x in s.get("facts", [])], "chart": chart, "builds": builds})
        deck = {"run": run.name, "lang": lang, "slug": sb.get("slug") or meta.get("slug"), "parts": len(road), "slides": slides}
        if (run / "podcast" / "plan.json").is_file():          # the podcast video: motion and the story line
            words = sc.get("story") or {}
            chap = {s["part"]: s["fields"].get("text") for s in slides if s["template"] == "chapter"}
            deck["motion"] = True
            deck["story"] = [{"id": p, "label": r(words.get(p, {}).get("label", "")), "takeaway": r(words.get(p, {}).get("takeaway", "")),
                              "question": chap.get(p)} for p in road] if words else None
        write_json(run / "slides" / f"{lang}.resolved.json", deck)
        written[lang] = len(slides)
    return written


# ------------------------------------------------------------------ the studio server

def _up() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def serve() -> None:
    """Start the studio's dev server if it isn't answering; it is left running for the next call. Call under the lock."""
    if _up():
        return
    path = os.environ.get("PATH", "")
    npm = str(Path.home() / ".npm-global" / "bin")
    env = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "PATH": f"{npm}:{path}" if npm not in path else path}
    logf = open(CACHE / "studio-server.log", "w")
    p = subprocess.Popen("pnpm tokens && pnpm --filter @articles/studio exec next dev -p %d -H 127.0.0.1" % PORT, shell=True,
                         cwd=ARTICLES, env=env, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    (CACHE / "studio-server.pid").write_text(str(p.pid))
    for _ in range(180):
        if _up():
            return
        time.sleep(1)
    die(f"the studio did not start on port {PORT}; see {CACHE / 'studio-server.log'}")


def stop() -> dict:
    import signal
    pidf = CACHE / "studio-server.pid"
    if not pidf.exists():
        return {"stopped": False}
    try:
        os.killpg(int(pidf.read_text()), signal.SIGTERM)
    except (ProcessLookupError, ValueError):
        pass
    pidf.unlink()
    return {"stopped": True}


def shoot(run_id: str, langs: tuple[str, ...] = ("en", "ko"), only: list[str] | None = None) -> dict:
    """Resolve, render every slide and step, and the contact sheets."""
    from playwright.sync_api import sync_playwright
    run = run_dir(run_id)
    resolve(run)
    frames, problems = [], {}
    old = read_json(run / "slides" / "render.json", {}) or {}
    rails = dict(old.get("rail") or {}) if only else {}
    with flock_file(CACHE / "studio.lock"):
        serve()
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            # No JavaScript: the slides are the server's render. Hydrated charts re-measure their width and would undo
            # the studio's uniform scaling (studio.css .vs-chart).
            ctx = b.new_context(java_script_enabled=False, viewport={"width": 1920, "height": 1080})
            pg = ctx.new_page()
            for lang in langs:
                deck = read_json(run / "slides" / f"{lang}.resolved.json")
                folder = run / "slides" / lang
                folder.mkdir(parents=True, exist_ok=True)
                for s in deck["slides"]:
                    if only and s["id"] not in only:
                        continue
                    for step in range(1, s["steps"] + 1):
                        pg.goto(f"http://127.0.0.1:{PORT}/{run.name}/{lang}/{s['id']}?step={step}", wait_until="networkidle")
                        pg.wait_for_timeout(250)              # fonts (no script, so no document.fonts.ready)
                        pg.evaluate(FIT_JS)
                        p = folder / f"{s['id']}-{step}.png"
                        clip = _motion(pg, p) if deck.get("motion") else None
                        pg.screenshot(path=str(p), clip={"x": 0, "y": 0, "width": 1920, "height": 1080})
                        spill = pg.evaluate(SPILL_JS)
                        rail = pg.evaluate(RAIL_JS) if deck.get("story") else {}
                        if rail:
                            rails[lang] = rail
                        frames.append({"lang": lang, "slide": s["id"], "step": step, "template": s["template"], "file": str(p),
                                       **({"clip": clip} if clip else {}), **({"rail": True} if rail else {})})
                        if spill:
                            problems[f"{lang} {s['id']}·{step}"] = spill
                _sheet(b, run, lang, [f for f in frames if f["lang"] == lang] if not only else None)
            b.close()
    if only:                                   # keep the sheet whole: rebuild it from every frame on disk
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for lang in langs:
                _sheet(b, run, lang, None)
            b.close()
    if only:                                   # a partial render keeps the other frames' records
        done = {(f["lang"], f["slide"], f["step"]) for f in frames}
        frames = [f for f in old.get("list", []) if (f["lang"], f["slide"], f["step"]) not in done] + frames
    rec = {"frames": len(frames), "clips": sum(1 for f in frames if f.get("clip")), "problems": problems,
           "sheets": [str(run / "slides" / f"{lang}-sheet.png") for lang in langs]}
    write_json(run / "slides" / "render.json", {**rec, "rail": rails, "list": frames})
    return rec


def _motion(pg, png: Path) -> dict | None:
    """The step's enter animation as a clip next to its PNG: every animation paused, stepped to each frame's time and
    screenshot into a temporary folder, encoded at 30 fps; the page is left at the last frame for the PNG. None when
    nothing on the slide moves (a chart's highlight step: the assembly cross-fades to it)."""
    end = pg.evaluate(PAUSE_JS)
    mp4 = png.with_suffix(".mp4")
    if not end:
        mp4.unlink(missing_ok=True)
        return None
    n = int(end * FPS / 1000) + 2
    with tempfile.TemporaryDirectory(prefix="vs-motion-") as tmp:
        for k in range(n):
            pg.evaluate(SEEK_JS, min(end, k * 1000 / FPS))
            pg.screenshot(path=f"{tmp}/{k:03d}.jpg", type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": 1920, "height": 1080})
        r = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", f"{tmp}/%03d.jpg",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", str(mp4)],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"{mp4.name}: ffmpeg failed: {r.stderr[-400:]}")
    pg.evaluate(SEEK_JS, end)
    return {"file": str(mp4), "seconds": round(n / FPS, 2)}


def _sheet(browser, run: Path, lang: str, frames: list[dict] | None) -> None:
    """The contact sheet from the frames themselves: four across, in storyboard order, each captioned."""
    import html
    deck = read_json(run / "slides" / f"{lang}.resolved.json")
    cells = []
    for s in deck["slides"]:
        for step in range(1, s["steps"] + 1):
            p = run / "slides" / lang / f"{s['id']}-{step}.png"
            if p.is_file():
                cap = f"{s['id']}{'·' + str(step) if s['steps'] > 1 else ''} {s['template']} · {s['part']}"
                cells.append(f'<figure><img src="{p.as_uri()}"><figcaption>{html.escape(cap)}</figcaption></figure>')
    page = ("<!doctype html><meta charset=utf-8><style>body{margin:0;background:#000}main{display:grid;"
            "grid-template-columns:repeat(4,480px);gap:36px 24px;padding:32px}figure{margin:0}img{width:480px;height:270px;"
            "display:block;outline:1px solid #244758}figcaption{margin-top:8px;font:500 16px/22px monospace;color:#ccc}</style>"
            "<main>" + "".join(cells) + "</main>")
    tmp = run / "slides" / f".{lang}-sheet.html"
    tmp.write_text(page, encoding="utf-8")
    pg = browser.new_context(java_script_enabled=False, viewport={"width": 2072, "height": 800}).new_page()
    pg.goto(tmp.as_uri(), wait_until="load")
    pg.screenshot(path=str(run / "slides" / f"{lang}-sheet.png"), full_page=True)
    pg.close()
    tmp.unlink()
