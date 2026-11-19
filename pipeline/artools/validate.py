"""Stage outputs against contracts/*.schema.json, plus the rules a schema can't express."""
from __future__ import annotations

import json
from pathlib import Path

from .paths import CONFIG, CONTRACTS, load_yaml, read_json, read_jsonl

_schemas: dict = {}


def schema(name: str) -> dict:
    if name not in _schemas:
        _schemas[name] = json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))
    return _schemas[name]


def check(obj, name: str, where: str) -> list[str]:
    import jsonschema
    v = jsonschema.Draft7Validator(schema(name))
    return [f"{where}: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message[:200]}" for e in v.iter_errors(obj)]


def _file(run: Path, rel: str, name: str) -> tuple[object, list[str]]:
    p = run / rel
    if not p.exists():
        return None, [f"{rel} is missing"]
    try:
        obj = read_json(p)
    except json.JSONDecodeError as e:
        return None, [f"{rel}: invalid JSON ({e})"]
    return obj, check(obj, name, rel)


def _skipped(run: Path, rel_log: str) -> bool:
    log = read_json(run / rel_log, {}) or {}
    return bool(log.get("skipped"))


def validate_stage(stage: str, run: Path) -> list[str]:
    scout = stage.startswith("scout:")
    base_stage = stage.split(":", 1)[-1]
    probs: list[str] = []
    if stage == "frame-question":
        _, probs = _file(run, "brief.v1.json", "brief")
    elif base_stage == "search-jejualps":
        rel = "scout/evidence-jejualps.jsonl" if scout else "evidence/jejualps.jsonl"
        rows = read_jsonl(run / rel)
        if not rows:
            return [f"{rel} is missing or empty"]
        for i, e in enumerate(rows):
            probs += check(e, "evidence", f"{rel}:{i + 1}")
            if e.get("quote") and not e.get("verified"):
                probs.append(f"{rel}:{i + 1}: quote not verified ({e['id']}); verify it or drop the quote")
        if not scout and sum(1 for e in rows if e.get("verified")) < 5:
            probs.append(f"{rel}: fewer than 5 evidence records with a verified quote")
    elif base_stage.startswith("fetch-"):
        provider = {"fetch-fred": "fred", "fetch-ecos": "ecos", "fetch-public-data": None}[base_stage]
        root = run / ("scout/data" if scout else "data")
        logname = f"{provider or 'public-data'}.log.json"
        dirs = [root / provider] if provider else [root / "ecb", root / "eurostat"]
        cats = [d / "catalog.json" for d in dirs if (d / "catalog.json").exists()]
        logrel = (Path("scout/data" if scout else "data") / (provider or "public-data") / logname)
        if not cats and not _skipped(run, str(logrel)):
            return [f"no catalog under {[str(d.relative_to(run)) for d in dirs]} and no skip logged in {logrel}"]
        for c in cats:
            for i, d in enumerate(read_json(c, [])):
                probs += check(d, "dataset", f"{c.relative_to(run)}:{i}")
                if d.get("validation", {}).get("verdict") == "fail" and not d["validation"].get("forced"):
                    probs.append(f"{d['id']}: validation failed")
    elif stage == "refine-question":
        rv, p1 = _file(run, "question-review.json", "question-review")
        br, p2 = _file(run, "brief.json", "brief")
        probs = p1 + p2
        if rv:
            for pr in rv.get("premises", []):
                if pr.get("status") in ("supported", "partly", "contradicted") and not (pr.get("evidence") or pr.get("data")):
                    probs.append(f"premise {pr.get('id')}: status {pr['status']} needs scout evidence or data ids")
            if br and len(br.get("subquestions", [])) > 5:
                probs.append("brief.json: more than five sub-questions")
    elif stage == "map-literature":
        lm, probs = _file(run, "litmap.json", "litmap")
        if lm:
            ev = {e["id"] for e in read_jsonl(run / "evidence" / "jejualps.jsonl")}
            for p in (run / "evidence").glob("*.jsonl"):
                ev |= {e["id"] for e in read_jsonl(p)}
            for m in lm.get("mechanisms", []):
                for e in m.get("evidence", []):
                    if e not in ev:
                        probs.append(f"mechanism {m['id']}: unknown evidence {e}")
    elif stage == "analyze-data":
        an, probs = _file(run, "analysis/analysis.json", "analysis")
        if not (run / "analysis" / "analysis.py").exists():
            probs.append("analysis/analysis.py is missing")
        if an:
            from .content import load_run
            ds = load_run(run)["datasets"]
            for f in an.get("facts", []):
                for i in f.get("inputs", []):
                    if i not in ds:
                        probs.append(f"{f['id']}: input {i} is not a dataset in the run")
                    elif not ds[i].get("publishable") and f.get("publishable"):
                        probs.append(f"{f['id']}: marked publishable but input {i} is not")
    elif stage == "plan-article":
        pl, probs = _file(run, "plan.json", "plan")
        if pl:
            facts = {f["id"]: f for f in (read_json(run / "analysis/analysis.json", {}) or {}).get("facts", [])}
            for s in pl.get("sections", []):
                for u in s.get("uses", []):
                    if u.startswith("F") and u[1:].isdigit():
                        if u not in facts:
                            probs.append(f"section {s['id']}: unknown fact {u}")
                        elif not facts[u].get("publishable"):
                            probs.append(f"section {s['id']}: fact {u} is not publishable")
            # topics: one to three subjects, the main one first, and at most one region (config/topics.yaml groups)
            reg = {t["id"]: t for t in (load_yaml(CONFIG / "topics.yaml") or {}).get("topics", [])}
            chosen = pl.get("topics", [])
            regions = sum((reg.get(t.get("id")) or t).get("group") == "regions" for t in chosen)
            subjects = len(chosen) - regions
            if not 1 <= subjects <= 3 or regions > 1:
                probs.append(f"topics: choose one to three subject topics (the main one first) and at most one region from "
                             f"config/topics.yaml; this plan has {subjects} subject(s) and {regions} region(s)")
    elif stage == "draft-article":
        for lang in ("en", "ko"):
            if (run / "draft" / f"{lang}.json").exists() or lang == "en":
                _, p = _file(run, f"draft/{lang}.json", "draft")
                probs += p
        from .checks import check_numbers
        r = check_numbers(run)
        probs += [f"numbers: {x}" for x in r["blocking"]]
    elif stage == "make-charts":
        pl = read_json(run / "plan.json", {}) or {}
        for f in pl.get("figures", []):
            ch, p = _file(run, f"charts/{f['id']}.json", "chart")
            probs += p
        from .checks import check_charts
        probs += [f"charts: {x}" for x in check_charts(run)["blocking"]]
    elif stage == "review-article":
        _, probs = _file(run, "review.json", "review")
    elif stage == "make-cover":
        _, probs = _file(run, "cover/cover.json", "cover")
        from .cover import check as check_cover
        probs += [f"cover: {x}" for x in check_cover(run)["blocking"]]
    elif stage == "make-pdf":
        rec, probs = _file(run, "pdf/pdf.json", "pdf")
        from .pdf import check as check_pdf
        res = check_pdf(run)
        probs += [f"pdf: {x}" for x in res["blocking"]]
        if rec:
            seen = {e.get("lang") for e in rec.get("editions", [])}
            probs += [f"pdf/pdf.json: no entry for the {lang} edition" for lang in res["pages"] if lang not in seen]
    elif stage == "write-video-script":
        from .video.script import check as check_video_script
        probs = [f"video-script: {x}" for x in check_video_script(run)["blocking"]]
    elif stage == "make-slides":
        rec, probs = _file(run, "slides/slides.json", "video/slides")
        ren = read_json(run / "slides" / "render.json", {}) or {}
        sb = read_json(run / "storyboard.json", {}) or {}
        want = 2 * sum(s.get("steps") or 1 for s in sb.get("slides", []))
        have = sum(1 for f in ren.get("list", []) if Path(f["file"]).is_file())
        if have < want:
            probs.append(f"slides: {have} frames rendered of {want}; run artools video slides {run.name}")
        ok = {a["frame"] for a in (rec or {}).get("accepted", [])}
        probs += [f"slides: {k}: {v}" for k, v in (ren.get("problems") or {}).items() if k not in ok]
        from .video.script import check as check_video_script
        probs += [f"video-script: {x}" for x in check_video_script(run)["blocking"]]
    elif stage == "review-video":
        _, probs = _file(run, "review.json", "review")
    elif stage == "publish-article":
        if not (run / "publish.json").exists():
            probs = ["publish.json is missing"]
    # stages of the sample pipelines (config/pipelines/, status: sample)
    elif stage in ("select-indicators", "select-paper", "cluster-themes", "design-model"):
        name, rel = {"select-indicators": ("indicators", "indicators.json"), "select-paper": ("selection", "selection.json"),
                     "cluster-themes": ("themes", "themes.json"), "design-model": ("model", "model.json")}[stage]
        obj, probs = _file(run, rel, name)
        if obj and stage == "cluster-themes":
            ids = {e.get("id") for e in read_jsonl(run / "evidence/jejualps.jsonl")}
            probs += [f"theme {t['id']}: unknown evidence {e}" for t in obj.get("themes", []) for e in t["evidence"] if e not in ids]
    elif stage in ("read-paper", "collect-speeches"):
        rows = read_jsonl(run / "evidence/jejualps.jsonl")
        for i, e in enumerate(rows):
            probs += check(e, "evidence", f"evidence/jejualps.jsonl:{i + 1}")
            if e.get("quote") and not e.get("verified"):
                probs.append(f"evidence/jejualps.jsonl:{i + 1}: quote not verified ({e['id']})")
        if sum(1 for e in rows if e.get("verified")) < (3 if stage == "read-paper" else 5):
            probs.append("evidence/jejualps.jsonl: too few evidence records with a verified quote")
        if stage == "read-paper":
            chosen = ((read_json(run / "selection.json", {}) or {}).get("chosen") or {}).get("doc")
            probs += [f"{e['id']} is not from the chosen paper {chosen}" for e in rows
                      if chosen and (e.get("doc") or {}).get("ref") != chosen and e.get("kind") != "context"]
    return probs
