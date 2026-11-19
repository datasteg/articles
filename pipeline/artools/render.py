"""Screenshots of the run's charts as readers will see them: the real web components, served from .preview/."""
from __future__ import annotations

import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from .content import preview
from .paths import ARTICLES, CACHE, PREVIEW, die, read_json, run_dir
from .runlib import flock_file

PORT = int(os.environ.get("ARTICLES_PREVIEW_PORT", "3311"))
WIDTHS = (1040, 375)


def _up(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _env(content_dir: Path = PREVIEW) -> dict:
    path = os.environ.get("PATH", "")
    npm = str(Path.home() / ".npm-global" / "bin")
    return {**os.environ, "CONTENT_DIR": str(content_dir), "PREVIEW": "1" if content_dir == PREVIEW else "",
            "NEXT_TELEMETRY_DISABLED": "1", "PATH": f"{npm}:{path}" if npm not in path else path}


def reindex(content_dir: Path = PREVIEW) -> None:
    """Regenerate the site's content index from .preview/ (the dev server reloads it). `artools pdf` points it at
    content/ while it prints published articles, then back."""
    subprocess.run(["node", "scripts/build-content-index.mjs"], cwd=ARTICLES, env=_env(content_dir), check=True,
                   stdout=subprocess.DEVNULL)


def serve(content_dir: Path = PREVIEW, port: int = PORT) -> None:
    """Make sure the shared preview site answers on the port, serving .preview/ (all runs' previews) or the given
    content folder, and regenerate its content index. The server is shared by parallel runs and left running;
    call under the lock."""
    if _up(port):
        reindex(content_dir)
        time.sleep(3)
        return None
    cmd = os.environ.get("ARTICLES_WEB_CMD",
                         f"pnpm tokens && pnpm index && pnpm --filter @articles/web exec next dev -p {port}")
    logf = open(ARTICLES / ".preview-server.log", "w")
    p = subprocess.Popen(cmd, shell=True, cwd=ARTICLES, env=_env(content_dir), stdout=logf, stderr=subprocess.STDOUT,
                         start_new_session=True)
    (CACHE / "preview-server.pid").write_text(str(p.pid))
    for _ in range(180):
        if _up(port):
            return None
        time.sleep(1)
    stop(p)
    die(f"the preview site did not start on port {port}; see {ARTICLES / '.preview-server.log'}")


def stop_server() -> dict:
    pidf = CACHE / "preview-server.pid"
    if pidf.exists():
        import signal
        try:
            os.killpg(int(pidf.read_text()), signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            pass
        pidf.unlink()
        return {"stopped": True}
    return {"stopped": False, "note": "no server started by artools"}


def stop(p: subprocess.Popen | None) -> None:
    if p:
        import signal
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def _open(b, lang: str, slug: str, theme: str, width: int):
    pg = b.new_page(viewport={"width": width + (0 if width < 600 else 160), "height": 900}, device_scale_factor=2)
    pg.goto(f"http://127.0.0.1:{PORT}/{lang}/a/{slug}?theme={theme}", wait_until="networkidle")
    try:
        pg.wait_for_function("() => [...document.querySelectorAll('figure[data-chart] .gl-chart')]"
                             ".every(e => e.dataset.ready === '1')", timeout=20000)
    except Exception:
        pass
    pg.wait_for_timeout(400)
    return pg


def slug_of(run: Path) -> str:
    pl = read_json(run / "plan.json", {}) or {}
    return pl.get("slug") or "preview-" + run.name


def charts(run_id: str, langs=("en", "ko"), themes=("light", "dark")) -> dict:
    from playwright.sync_api import sync_playwright
    run = run_dir(run_id)
    slug = slug_of(run)
    out_dir = run / "charts" / "render"
    out_dir.mkdir(parents=True, exist_ok=True)
    shots, missing = [], []
    with flock_file(CACHE / "preview-server.lock"):
        built = preview(run_id, slug)
        serve()
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for lang in [x for x in langs if x in built["editions"]]:
                for theme in themes:
                    for w in WIDTHS:
                        pg = _open(b, lang, slug, theme, w)
                        for cid in built["charts"]:
                            el = pg.query_selector(f"#fig-{cid}")
                            if not el:
                                missing.append(f"{lang}/{theme}/{w}: #fig-{cid}")
                                continue
                            p = out_dir / f"{cid}.{lang}.{theme}.{w}.png"
                            el.screenshot(path=str(p))
                            shots.append(str(p))
                        pg.close()
            b.close()
    return {"slug": slug, "screenshots": shots, "missing": missing, "dir": str(out_dir)}


def page(run_id: str, lang: str = "en", theme: str = "light", width: int = 1040) -> dict:
    """A full-page screenshot of the article, for the editor's gate-3 look and for review."""
    from playwright.sync_api import sync_playwright
    run = run_dir(run_id)
    slug = slug_of(run)
    p = run / "charts" / "render" / f"page.{lang}.{theme}.{width}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    with flock_file(CACHE / "preview-server.lock"):
        preview(run_id, slug)
        serve()
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = _open(b, lang, slug, theme, width)
            pg.screenshot(path=str(p), full_page=True)
            b.close()
    return {"screenshot": str(p), "url": f"http://127.0.0.1:{PORT}/{lang}/a/{slug}"}


def cover(run_id: str, themes=("light", "dark")) -> dict:
    """The run's cover where readers meet it, for make-cover's look before it finishes: its card in the Latest list
    (1040 and 375 px, both themes), the tile alone enlarged, and the list with its neighbours."""
    from playwright.sync_api import sync_playwright
    run = run_dir(run_id)
    slug = slug_of(run)
    out_dir = run / "cover" / "render"
    out_dir.mkdir(parents=True, exist_ok=True)
    shots, missing = [], []
    with flock_file(CACHE / "preview-server.lock"):
        built = preview(run_id, slug)
        if not built.get("cover"):
            die("no cover to render: write cover/cover.svg and pass `artools check cover` first",
                problems=built.get("cover_problems", ["cover/cover.svg is missing"]))
        serve()
        lang = "en" if "en" in built["editions"] else built["editions"][0]
        card_sel = f'article.gl-story:has(a[href="/{lang}/a/{slug}"])'
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for theme in themes:
                for w in WIDTHS:
                    for scale, what in ((2, "card"), (4, "tile")) if w == WIDTHS[0] else ((2, "card"),):
                        pg = b.new_page(viewport={"width": w + (0 if w < 600 else 160), "height": 1400}, device_scale_factor=scale)
                        pg.goto(f"http://127.0.0.1:{PORT}/{lang}?theme={theme}", wait_until="networkidle")
                        el = pg.query_selector(card_sel + (" .gl-story__thumb" if what == "tile" else ""))
                        if not el:
                            missing.append(f"{what} {theme}/{w}: no card for {slug} on /{lang}")
                        else:
                            p = out_dir / (f"tile.{theme}.png" if what == "tile" else f"card.{theme}.{w}.png")
                            el.screenshot(path=str(p))
                            shots.append(str(p))
                        if what == "card" and theme == "light" and w == WIDTHS[0]:
                            feed = pg.query_selector(".home__feed")
                            if feed:
                                p = out_dir / "list.light.1040.png"
                                feed.screenshot(path=str(p))
                                shots.append(str(p))
                        pg.close()
            b.close()
    return {"slug": slug, "screenshots": shots, "missing": missing, "dir": str(out_dir)}
