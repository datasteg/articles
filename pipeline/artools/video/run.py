"""A video run: the published article copied in, its facts, and the manifest the driver follows.

/data/articles/runs/<date>-<slug>-video/
  run.json      type video, pipeline video, the article's slug, commit and content hash
  source/       content/articles/<slug>/ as published (meta, editions, sources, charts, data, cover)
  source/facts.json  the article run's publishable facts, with labels and display rules (for fact tokens)
  storyboard.json, script/<lang>.json, slides/, audio/, asr/, video/, review/, youtube/, logs/"""
from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import subprocess

from .. import pipelines, runlib
from ..paths import ARTICLES, CONTENT, RUNS, die, read_json, run_dir, write_json
from . import cfg

SUBDIRS = ("source", "script", "slides", "audio", "asr", "video", "review", "youtube", "logs", "podcast")
DEFAULT_RUNTIME = ("claude-opus-5-5", "high")          # the judgement stages; make-slides asks for Sonnet


def content_hash(folder) -> str:
    h = hashlib.sha256()
    for p in sorted(x for x in folder.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(folder)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _commit() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ARTICLES), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def start(slug: str, run_id: str | None = None, model: str | None = None, effort: str | None = None,
          mode: str | None = None, replaces: str | None = None) -> dict:
    src = CONTENT / "articles" / slug
    meta = read_json(src / "meta.json")
    if not meta:
        die(f"no published article {slug} in {CONTENT / 'articles'}")
    if not (meta.get("review") or {}).get("approved"):
        die(f"{slug} is not approved: a video starts from a published article")
    missing = [lang for lang in ("en", "ko") if not (src / f"{lang}.json").is_file()]
    if missing:
        die(f"{slug} has no {missing} edition: the video needs both")
    mode = mode or cfg("podcast").get("default_mode") or "narrated"
    p = pipelines.load("video-podcast" if mode == "podcast" else "video")
    rid = run_id or f"{dt.date.today():%Y%m%d}-{slug}-video"
    n = 2
    while (RUNS / rid).exists() and not run_id:
        rid = f"{dt.date.today():%Y%m%d}-{slug}-video-{n}"
        n += 1
    run = RUNS / rid
    if run.exists():
        die(f"run {rid} exists", run=str(run))
    for sub in SUBDIRS:
        (run / sub).mkdir(parents=True)
    shutil.copytree(src, run / "source", dirs_exist_ok=True, ignore=shutil.ignore_patterns("pdf"))

    # Fact tokens need each fact's display rules and label, which the article run keeps (meta.json keeps values only).
    published = {f["id"] for f in meta.get("facts", [])}
    art_run = (meta.get("run") or {}).get("id")
    an = read_json(RUNS / art_run / "analysis" / "analysis.json", {}) if art_run else {}
    facts = [f for f in (an or {}).get("facts", []) if f.get("id") in published and f.get("publishable", True)]
    note = None
    if not facts:
        facts, note = meta.get("facts", []), f"the article run {art_run} has no analysis.json: facts without display rules"
    write_json(run / "source" / "facts.json", {"from": art_run, "facts": facts})

    m, e = model or DEFAULT_RUNTIME[0], effort or DEFAULT_RUNTIME[1]
    manifest = {"id": rid, "type": "video", "question": f"Video of {slug}", "created": runlib.now(),
                "pipeline": p["id"], "pipeline_version": str(p["version"]), "mode": mode,
                "source": {"slug": slug, "commit": _commit(), "content_hash": content_hash(src), "article_run": art_run},
                "runtime": runlib._runtime(m, e), "stages": {}, "gates": {g: runlib._gate() for g in pipelines.gates(p)}}
    if replaces:   # a correction's new revision: finish unlists the older video run once both editions are up
        if not (RUNS / replaces / "run.json").is_file():
            die(f"no video run {replaces} to replace")
        manifest["replaces"] = replaces
    write_json(run / "run.json", manifest)
    return {"run": rid, "path": str(run), "slug": slug, "facts": len(facts), "note": note,
            "next": f"artools drive {rid} --allow-sample"}


def status(run_id: str) -> dict:
    run = run_dir(run_id)
    m = read_json(run / "run.json", {}) or {}
    if m.get("type") != "video":
        die(f"{run_id} is not a video run")
    src = CONTENT / "articles" / m["source"]["slug"]
    now_hash = content_hash(src) if src.is_dir() else None
    files = {
        "storyboard": (run / "storyboard.json").is_file(),
        "scripts": sorted(p.stem for p in (run / "script").glob("*.json")),
        "slides": len(list((run / "slides").rglob("*.png"))),
        "audio": len(list((run / "audio").rglob("*.wav"))) + len(list((run / "audio").glob("*.m4a"))),
        "videos": sorted(p.name for p in (run / "video").glob("*.mp4")),
    }
    return {"run": run.name, "slug": m["source"]["slug"], "stages": {k: v.get("state") for k, v in m["stages"].items()},
            "gates": {k: v.get("approved") for k, v in m["gates"].items()}, "files": files,
            "article_changed": bool(now_hash and now_hash != m["source"]["content_hash"])}


def auto(slug: str, mode: str | None = None, replaces: str | None = None) -> dict:
    """The explainer's `video` step: a video run for a live article, driven in the background to its public upload.
    `replaces`: the older video run of the same article that this revision retires (unlisted after the upload)."""
    import os
    res = start(slug, mode=mode, replaces=replaces)
    run = RUNS / res["run"]
    log = run / "logs" / "drive.out"
    with log.open("w") as f:
        p = subprocess.Popen(["artools", "drive", res["run"]], cwd=ARTICLES, stdout=f, stderr=subprocess.STDOUT,
                             start_new_session=True, env={**os.environ})
    (run / "logs" / "drive.pid").write_text(str(p.pid))
    return {"run": res["run"], "slug": slug, "pid": p.pid, "log": str(log),
            "follow": f"artools video status {res['run']}", "channel": "https://www.youtube.com/@datasteg"}
