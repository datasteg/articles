"""Publish an approved run end to end, safely when several runs finish at once: under one machine-wide lock,
write content/, print its PDF editions, check it, commit on main, push, ds deploy, verify; revert the commit if the
deploy fails. Then remove this app's older images from the dev machine: every deploy builds one, and only the live
one is needed."""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from . import pipelines, runlib
from . import pdf as pdf_edition
from .content import publish
from .paths import ARTICLES, CACHE, die, read_json, run_dir, write_json
from .render import _env, slug_of

REPO = ARTICLES.parent
SITE = "https://articles.datasteg.com"
TRAILER = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def sh(cmd: list[str], cwd: Path = REPO, log: Path | None = None, check: bool = True, timeout: int = 1800) -> str:
    r = subprocess.run(cmd, cwd=cwd, env=_env() | {"CONTENT_DIR": "", "PREVIEW": ""}, capture_output=True, text=True, timeout=timeout)
    if log:
        with log.open("a", encoding="utf-8") as f:
            f.write(f"$ {' '.join(cmd)}\n{r.stdout}\n{r.stderr}\n")
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])} failed ({r.returncode}): {(r.stderr or r.stdout)[-800:]}")
    return r.stdout.strip()


def next_tag(log: Path) -> str:
    today = dt.date.today().strftime("%Y%m%d")
    cur = live_tag(log) or "-"
    n = int(cur.split(".")[1]) + 1 if cur.startswith(today + ".") and cur.split(".")[1].isdigit() else 1
    return f"{today}.{n}"


def live_tag(log: Path | None = None) -> str | None:
    status = sh(["ds", "status"], cwd=ARTICLES, log=log, check=False)
    m = re.search(r"^articles\s*\n\s*current:\s*(\S+)", status, re.M)
    return m.group(1) if m else None


def prune_images(keep: str | None = None, log: Path | None = None) -> dict:
    """Remove this app's local images except the live tag. `ds deploy` leaves each release's image on the dev
    machine (about 250 MB each); the server keeps its own current and previous tags for `ds rollback`, so nothing
    here needs the old ones. Run under the publish lock, so it never races a deploy."""
    keep = keep or live_tag(log)
    if not keep:
        return {"kept": None, "removed": [], "note": "live tag unknown (ds status failed); nothing removed"}
    refs = sh(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], cwd=ARTICLES, log=log, check=False).splitlines()
    old = [r for r in refs if re.search(r"(^|/)(datasteg-)?articles:", r) and not r.endswith(f":{keep}")]
    if old:
        sh(["docker", "image", "rm", *old], cwd=ARTICLES, log=log, check=False)
    return {"kept": keep, "removed": old}


def _ok(url: str, tries: int = 24) -> int:
    code = 0
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "artools ship"}), timeout=15) as r:
                code = r.status
                if code == 200:
                    return code
        except Exception as e:
            code = getattr(e, "code", 0) or 0
        time.sleep(5)
    return code


def ship(run_id: str, slug: str | None = None, tag: str | None = None, dry_run: bool = False) -> dict:
    run = run_dir(run_id)
    m = runlib.load(run)
    if not m["gates"]["publish"].get("approved"):
        die("gate 3 (publish) is not approved")
    pl = pipelines.of_run(run)
    if "make-cover" in pipelines.skills(pl) and (m.get("stages", {}).get("make-cover") or {}).get("state") != "done":
        die(f"no cover yet: the {pl['id']} pipeline makes the list's picture before publishing. Run "
            f"`artools drive {run.name} --only make-cover`, look at cover/render/, then ship again")
    if "make-pdf" in pipelines.skills(pl) and (m.get("stages", {}).get("make-pdf") or {}).get("state") != "done":
        die(f"no PDF proof yet: the {pl['id']} pipeline proofs the PDF edition before publishing. Run "
            f"`artools drive {run.name} --only make-pdf`, look at pdf/render/, then ship again")
    slug = slug or slug_of(run)
    log = run / "logs" / "ship.log"
    from .runlib import flock_file
    with flock_file(CACHE / "publish.lock"):
        try:
            branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], log=log)
            if branch != "main":
                die(f"the working folder is on {branch}, not main")
            sh(["git", "pull", "--ff-only", "--quiet"], log=log)
            # The commit holds only articles/content. Other folders' unstaged work (another session's) stays out of it
            # and cannot block a ship; anything staged, or any change under articles/, still does.
            status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout
            dirty = [l for l in status.splitlines()      # not sh(): it strips the first line's leading status column
                     if l.strip() and (l[0] not in " ?" or l[3:].strip('"').startswith("articles/"))]
            if dirty:
                die("the working folder has uncommitted changes; publishing commits only the article", changes=dirty[:20])
            def undo():
                sh(["git", "checkout", "--", "articles/content"], log=log, check=False)
                sh(["git", "clean", "-fdq", "articles/content"], log=log, check=False)
            res = publish(run_id, slug)
            try:
                res["pdf"] = pdf_edition.publish([slug])["printed"][slug]   # each edition printed from content/
                sh(["node", "scripts/check-content.mjs"], cwd=ARTICLES, log=log)   # production rules: approval, refs, charts, PDFs
                # Korean gate: the site's UI Korean is from qkr (tools/ko-refine); article prose is outside it
                sh(["python3", str(REPO / "tools" / "ko-refine" / "ko_refine.py"), "verify", "--service", "articles", "--strict"], log=log)
            except Exception as e:   # a failed check, or the browser failing while it prints
                undo()
                raise e if isinstance(e, RuntimeError) else RuntimeError(f"{type(e).__name__}: {e}")
            if dry_run:
                undo()
                return {"dry_run": True, "slug": slug, **res}
            sh(["git", "add", "articles/content"], log=log)
            title = (read_json(ARTICLES / "content" / "articles" / slug / "en.json", {}) or {}).get("title", slug)
            msg = f"article: {slug}\n\n{title}\nRun {run.name}, approved by {m['gates']['publish'].get('by')}.\n\n{TRAILER}"
            sh(["git", "commit", "-q", "-m", msg], log=log)
            commit = sh(["git", "rev-parse", "--short", "HEAD"], log=log)
            sh(["git", "push", "-q", "origin", "main"], log=log)
            tag = tag or next_tag(log)
            try:
                sh(["ds", "deploy", "articles", tag], cwd=ARTICLES, log=log, timeout=3600)
            except RuntimeError as e:
                sh(["git", "revert", "--no-edit", "HEAD"], log=log)
                sh(["git", "push", "-q", "origin", "main"], log=log)
                die(f"ds deploy failed; commit {commit} reverted and pushed. See {log}", detail=str(e)[-600:])
            health = _ok(f"{SITE}/health")
            page = _ok(f"{SITE}/en/a/{slug}")
            out = {"slug": slug, "commit": commit, "tag": tag, "deployed_at": runlib.now(),
                   "url": f"{SITE}/en/a/{slug}", "url_ko": f"{SITE}/ko/a/{slug}", "health": health, "page": page,
                   "pdf": {lang: {"url": f"{SITE}/pdf/{slug}-{lang}.pdf", "pages": r["pages"],
                                  "status": _ok(f"{SITE}/pdf/{slug}-{lang}.pdf", tries=3)} for lang, r in res.get("pdf", {}).items()}}
            left = (read_json(run / "review.json", {}) or {}).get("blocking") or []
            if left:              # published anyway (editorial.yaml → gates.on_blocking): the editor's review list
                out["review_left"] = [{"where": b.get("where"), "issue": (b.get("issue") or "")[:300]} for b in left]
            if res.get("cover_problems"):
                out["cover_left_out"] = res["cover_problems"]
            prev = read_json(run / "publish.json", {}) or {}
            if prev.get("tag"):   # an update: keep the earlier publications
                out["previous"] = [*(prev.get("previous") or []), {k: prev.get(k) for k in ("commit", "tag", "deployed_at")}]
            write_json(run / "publish.json", out)
            runlib.set_stage(run, "publish-article", state="done", ended=runlib.now(), note=f"deployed {tag}")
            out["images_removed"] = len(prune_images(tag, log)["removed"])
            return out
        except RuntimeError as e:
            die(str(e), log=str(log))
