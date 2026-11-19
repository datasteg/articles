"""Article types and their pipelines: config/pipelines/<type>.yaml.

One file per type is the single source for three things: the steps `artools drive` runs, the diagram the site draws
("How we work" and each article type's method page), and docs/PIPELINES.md. A run follows the pipeline named in its
run.json (`pipeline`, default explainer); `run_stats` counts what each step produced."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .paths import CONFIG, SKILLS, read_json

DIR = CONFIG / "pipelines"
# Pipelines the site must not draw (derived products): outside config/pipelines/, so
# build-content-index.mjs never reads them, but the driver and `artools pipelines check` do.
PRIVATE = {"video": CONFIG / "video" / "pipeline.yaml", "video-podcast": CONFIG / "video" / "podcast-pipeline.yaml"}
DEFAULT = "explainer"
TZ = "Asia/Seoul"
KINDS = ("skill", "sources", "fetch", "gate", "command", "desk")   # desk: a step of the data desk (artools/desk/run.py)


def ids() -> list[str]:
    """The public article types (config/pipelines/)."""
    return sorted(p.stem for p in DIR.glob("*.yaml"))


def load(pid: str) -> dict:
    f = PRIVATE.get(pid) or DIR / f"{pid}.yaml"
    if not f.is_file():
        raise SystemExit(json.dumps({"error": f"no pipeline {pid}", "pipelines": ids()}))
    return yaml.safe_load(f.read_text(encoding="utf-8"))


def of_run(run: Path) -> dict:
    return load((read_json(run / "run.json", {}) or {}).get("pipeline") or DEFAULT)


def gates(p: dict) -> list[str]:
    return [s["gate"] for s in p["steps"] if "gate" in s]


def skills(p: dict) -> list[str]:
    """Every stage skill the pipeline runs (source skills are routed at run time)."""
    out = [s["skill"] for s in p["steps"] if s.get("skill")]
    out += [o for s in p["steps"] for o in (s.get("loop") or {}).get("owners", [])]
    return list(dict.fromkeys(out))


def check(p: dict) -> list[str]:
    """Problems that would break the driver or the site's diagram."""
    probs = []
    for k in ("id", "version", "status", "name", "tagline", "shape", "phases", "steps"):
        if k not in p:
            probs.append(f"missing {k}")
    if probs:
        return probs
    if p["status"] not in ("live", "sample"):
        probs.append(f"status is {p['status']}; live or sample")
    phases = [ph["id"] for ph in p["phases"]]
    seen = set()
    for s in p["steps"]:
        sid = s.get("id")
        if sid in seen:
            probs.append(f"step {sid} appears twice")
        seen.add(sid)
        if s.get("phase") not in phases:
            probs.append(f"step {sid}: phase {s.get('phase')} is not in phases")
        if sum(k in s for k in KINDS) != 1:
            probs.append(f"step {sid}: needs exactly one of {KINDS}")
        for f in ("label", "detail"):
            if f in s and not all((s[f] or {}).get(lang) for lang in ("en", "ko")):
                probs.append(f"step {sid}: {f} needs en and ko")
        if "label" not in s:
            probs.append(f"step {sid}: no label")
        if s.get("skill") and p["status"] == "live" and not (SKILLS / s["skill"] / "SKILL.md").is_file():
            probs.append(f"step {sid}: skill {s['skill']} does not exist")
        for o in (s.get("loop") or {}).get("owners", []):
            if o not in [x.get("skill") for x in p["steps"]]:
                probs.append(f"step {sid}: loop owner {o} is not a step of this pipeline")
    # the editor's publish step (manual: true) ends what the driver runs; only follow-ups (`follows: publish`,
    # e.g. the video, started by publish-article) may come after it
    core = [x for x in p["steps"] if not x.get("follows")]
    if core and not core[-1].get("manual"):
        probs.append("the last step before any follow-up should be the editor's publish step (manual: true)")
    if any(x.get("follows") for x in core[:-1] if x) or any(not x.get("follows") for x in p["steps"][len(core):]):
        probs.append("follow-up steps (follows: publish) must all come after the publish step")
    if p["shape"].get("gates") != len(gates(p)):
        probs.append(f"shape.gates is {p['shape'].get('gates')} but the pipeline has {len(gates(p))} gates")
    missing = [sk for sk in skills(p) if not (SKILLS / sk / "SKILL.md").is_file()]
    if missing and p["status"] == "live":
        probs.append(f"skills missing: {missing}")
    return probs


def mermaid(p: dict, lang: str = "en") -> str:
    """The pipeline as a Mermaid flowchart: one subgraph per phase, gates as diamonds, loops as dotted returns."""
    lines = ["flowchart LR"]
    prev = None
    for ph in p["phases"]:
        lines.append(f'  subgraph ph_{ph["id"].replace("-", "_")}["{ph["label"][lang]}"]')   # ph_: phase and step ids may match
        lines.append("    direction TB")
        for s in [x for x in p["steps"] if x["phase"] == ph["id"]]:
            nid, label = s["id"].replace("-", "_"), s["label"][lang]
            if s.get("branches"):
                label += "<br/><small>" + " · ".join(b[lang] for b in s["branches"]) + "</small>"
            shape = (f'{{"{label}"}}' if "gate" in s else f'[/"{label}"/]' if s.get("manual")
                     else f'[["{label}"]]' if s.get("branches") else f'["{label}"]')
            lines.append(f"    {nid}{shape}")
        lines.append("  end")
    for s in p["steps"]:
        nid = s["id"].replace("-", "_")
        if prev:
            lines.append(f"  {prev} --> {nid}")
        prev = nid
        loop = s.get("loop")
        if loop:
            by_skill = {x.get("skill"): x["id"].replace("-", "_") for x in p["steps"] if x.get("skill")}
            for o in loop["owners"]:
                if o in by_skill:
                    lines.append(f'  {nid} -. "fix, ≤{loop["max"]}" .-> {by_skill[o]}')
    gate_ids = [s["id"].replace("-", "_") for s in p["steps"] if "gate" in s]
    if gate_ids:
        lines.append("  classDef gate fill:#fff4d6,stroke:#b07d00")
        lines.append(f"  class {','.join(gate_ids)} gate")
    return "\n".join(lines)


def docs() -> str:
    """docs/PIPELINES.md: every type, its shape and its diagram, generated from config/pipelines/."""
    out = ["# Pipelines", "",
           "Generated by `artools pipelines docs` from `config/pipelines/*.yaml`; edit the YAML, not this file.", "",
           "| Type | Status | What it is | Length | Figures | Editor gates | Steps |", "|---|---|---|---|---|---|---|"]
    ps = [load(i) for i in ids()]
    ps.sort(key=lambda p: (p["status"] != "live", p["id"]))
    for p in ps:
        out.append(f"| `{p['id']}` | {p['status']} | {p['tagline']['en']} | {p['shape']['words']['en']} | "
                   f"{p['shape']['figures']} | {p['shape']['gates']} | {len(p['steps'])} |")
    for p in ps:
        new = [sk for sk in skills(p) if not (SKILLS / sk / "SKILL.md").is_file()]
        sample = [sk for sk in skills(p) if (SKILLS / sk / "SKILL.md").is_file()
                  and "status: sample" in (SKILLS / sk / "SKILL.md").read_text(encoding="utf-8")]
        out += ["", f"## {p['name']['en']} (`{p['id']}`, v{p['version']}, {p['status']})", "", p["tagline"]["en"] + ".", "",
                "```mermaid", mermaid(p), "```", ""]
        if sample or new:
            out.append("Skills still in draft: " + ", ".join(f"`{s}`" for s in sample + new) + ".")
    return "\n".join(out) + "\n"


def topics(chosen: list[dict]) -> list[dict]:
    """A plan's topics with their labels from config/topics.yaml (the shared list); unknown ids keep the plan's label."""
    known = {t["id"]: t for t in yaml.safe_load((CONFIG / "topics.yaml").read_text(encoding="utf-8"))["topics"]}
    return [{"id": t["id"], "label": known[t["id"]]["label"] if t["id"] in known else t.get("label")} for t in chosen]


# --- what each step produced, for the article's diagram ------------------------------------------------------------

def _lines(f: Path) -> list[dict]:
    if not f.is_file():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def _docs(evidence: list[dict]) -> int:
    return len({(e.get("doc") or {}).get("ref") if isinstance(e.get("doc"), dict) else e.get("doc") for e in evidence} - {None})


def _catalog(run: Path, sub: str = "data") -> tuple[int, list[str]]:
    n, providers = 0, []
    names = {"ecb": "ECB", "eurostat": "Eurostat", "fred": "FRED", "ecos": "Bank of Korea", "imf": "IMF", "bis": "BIS",
             "oecd": "OECD", "public-data": None, "derived": None}
    for c in sorted((run / sub).glob("*/catalog.json")):
        prov = c.parent.name
        if prov == "derived":
            continue
        items = read_json(c, []) or []
        items = items.get("datasets", []) if isinstance(items, dict) else items
        if items:
            n += len(items)
            name = names.get(prov, prov.upper())
            if name and name not in providers:
                providers.append(name)
    return n, providers


def _logs(run: Path, stage: str) -> int:
    from .logs import base, pruned, stage_logs
    names = [base(p) for p in stage_logs(run)] + list(pruned(run))
    return len({x for x in names if x.rsplit(".", 1)[0] == stage.replace(":", "_")})


def step_stats(run: Path, step: dict) -> dict:
    sk = step.get("skill")
    if step.get("sources") == "scout":
        ev = _lines(run / "scout" / "evidence-jejualps.jsonl")
        n, _ = _catalog(run, "scout/data")
        return {"docs": _docs(ev), "series": n}
    if step.get("fetch") == "routed":
        n, prov = _catalog(run)
        return {"series": n, "providers": prov}
    if step.get("desk"):       # the data desk's steps (artools/desk/): the same counts, from the desk's files
        d = step["desk"]
        if d == "data":
            n, _ = _catalog(run)
            return {"series": n}
        if d == "analyst":
            return {"facts": len((read_json(run / "analysis" / "analysis.json", {}) or {}).get("facts", []))}
        if d == "writer":
            return {"charts": len([c for c in (run / "charts").glob("*.json") if not c.name.endswith(".log.json")])}
        if d == "review":
            return {"rounds": (read_json(run / "review.json", {}) or {}).get("rounds")}
        if d == "korean":
            return {"strings": len((read_json(run / "desk" / "korean.json", {}) or {}).get("strings", []))}
        return {}
    if sk == "refine-question":
        return {"premises": len((read_json(run / "question-review.json", {}) or {}).get("premises", []))}
    if sk == "search-jejualps":
        ev = [e for e in _lines(run / "evidence" / "jejualps.jsonl") if e.get("mode", "deep") != "scout"]
        return {"docs": _docs(ev), "quotes": sum(1 for e in ev if e.get("verified") and e.get("quote"))}
    if sk == "map-literature":
        return {"mechanisms": len((read_json(run / "litmap.json", {}) or {}).get("mechanisms", []))}
    if sk == "analyze-data":
        return {"facts": len((read_json(run / "analysis" / "analysis.json", {}) or {}).get("facts", []))}
    if sk == "plan-article":
        plan = read_json(run / "plan.json", {}) or {}
        return {"sections": len(plan.get("sections", [])), "figures": len(plan.get("figures", []))}
    if sk == "make-charts":
        return {"charts": len([c for c in (run / "charts").glob("*.json") if not c.name.endswith(".log.json")])}
    if sk == "make-cover":
        return {"ideas": len((read_json(run / "cover" / "cover.json", {}) or {}).get("considered", []))}
    if sk == "make-pdf":
        eds = (read_json(run / "pdf" / "proof.json", {}) or {}).get("editions") or {}
        return {"pages": {lang: e["pages"] for lang, e in eds.items() if e.get("pages")}}
    if sk == "review-article":
        rv = read_json(run / "review.json", {}) or {}
        return {"rounds": rv.get("rounds") or _logs(run, "review-article")}
    return {}


def local_date(at: str | None) -> str | None:
    """A run.json UTC timestamp as the newsroom's date (Seoul), the calendar articles are dated in."""
    if not at:
        return None
    return dt.datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(ZoneInfo(TZ)).date().isoformat()


def run_stats(run: Path, words: dict | None = None) -> dict:
    """{"pipeline": {id, version}, "steps": {step id: counts}, "gates": {gate: {at, by}}} for meta.json."""
    p = of_run(run)
    m = read_json(run / "run.json", {}) or {}
    steps = {}
    for s in p["steps"]:
        st = step_stats(run, s)
        if (s.get("skill") == "draft-article" or s.get("desk") == "writer") and words:
            st = {**(st if s.get("desk") else {}), "words": words.get("en") or next(iter(words.values()), 0)}
        st = {k: v for k, v in st.items() if v}
        if st:
            steps[s["id"]] = st
    gates_ = {g: {"at": local_date(v.get("at")), "by": v.get("by")} for g, v in (m.get("gates") or {}).items() if v.get("approved")}
    return {"pipeline": {"id": p["id"], "version": str(p["version"])}, "steps": steps, "gates": gates_}
