"""run.json: the manifest of one run. Changed only here, under a lock, atomically."""
from __future__ import annotations

import datetime as dt
import fcntl
import re
from contextlib import contextmanager
from pathlib import Path

from .paths import RUNS, die, out, read_json, run_dir, write_json

STAGES = [
    "frame-question",
    "scout:search-jejualps", "scout:fetch-public-data", "scout:fetch-fred", "scout:fetch-ecos",
    "refine-question",
    "search-jejualps",
    "map-literature",
    "fetch-public-data", "fetch-fred", "fetch-ecos",
    "analyze-data",
    "plan-article",
    "draft-article",
    "make-charts",
    "review-article",
    "publish-article",
]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(text: str, n: int = 4) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    stop = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "is", "it", "how", "what", "be", "can", "could",
            "same", "as", "its", "does", "do", "will", "would", "this", "that", "with", "from", "by", "at", "or"}
    keep = [w for w in words if w not in stop][:n]
    return "-".join(keep) or "question"


@contextmanager
def flock_file(path: Path):
    """An exclusive lock shared by every artools process on this machine (parallel runs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("w")
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


@contextmanager
def locked(run: Path):
    lock = (run / ".run.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def load(run: Path) -> dict:
    m = read_json(run / "run.json")
    if m is None:
        die(f"{run} has no run.json")
    return m


def new(question: str, run_id: str | None = None, pipeline: str = "explainer", model: str | None = None,
        effort: str | None = None) -> dict:
    from . import pipelines
    p = pipelines.load(pipeline)
    rid = run_id or f"{dt.date.today():%Y%m%d}-{slugify(question)}"
    run = RUNS / rid
    if run.exists():
        die(f"run {rid} exists", run=str(run))
    for sub in ("scout", "evidence", "readings", "data", "analysis", "draft", "charts", "logs"):
        (run / sub).mkdir(parents=True)
    manifest = {"id": rid, "question": question, "created": now(), "pipeline": p["id"], "pipeline_version": str(p["version"]),
                "runtime": _runtime(model, effort), "stages": {}, "gates": {g: _gate() for g in pipelines.gates(p)}}
    write_json(run / "run.json", manifest)
    return {"run": rid, "path": str(run), "pipeline": p["id"], "runtime": manifest["runtime"]}


EFFORTS = ("low", "medium", "high", "xhigh", "max")


def _runtime(model: str | None, effort: str | None, note: str | None = None) -> dict:
    """The model and effort every stage session runs with (`claude -p --model --effort`). None means the CLI's default
    (~/.claude/settings.json), which is then not recorded: pass both to make runs comparable."""
    if effort and effort not in EFFORTS:
        die(f"effort {effort}: one of {EFFORTS}")
    return {"model": model, "effort": effort, "note": note,
            # subagents: paper-reader keeps its own model; fact-checker inherits the stage session's (.claude/agents/)
            "subagents": {"paper-reader": "sonnet", "fact-checker": "inherit"}}


def runtime(run_id: str, model: str | None = None, effort: str | None = None, note: str | None = None):
    """Show a run's runtime, or set it (for a run made before runtimes were recorded, or to switch model mid-run)."""
    run = run_dir(run_id)
    with locked(run):
        m = load(run)
        if model or effort or note:
            cur = m.get("runtime") or {}
            m["runtime"] = _runtime(model or cur.get("model"), effort or cur.get("effort"), note or cur.get("note"))
            write_json(run / "run.json", m)
    out({"run": run.name, "runtime": m.get("runtime")})


def _gate() -> dict:
    return {"approved": False, "by": None, "at": None, "note": None, "overrides": []}


def set_stage(run: Path, stage: str, **fields) -> dict:
    with locked(run):
        m = load(run)
        st = m["stages"].setdefault(stage, {})
        st.update(fields)
        write_json(run / "run.json", m)
        return st


def start(run_id: str, stage: str, version: str | None = None, model: str | None = None):
    run = run_dir(run_id)
    rt = load(run).get("runtime") or {}
    # the driver launched this session with the run's model and effort; a skill's own --model wins
    st = set_stage(run, stage, state="running", started=now(), ended=None, skill_version=version,
                   model=model or rt.get("model"), effort=rt.get("effort"))
    out({"run": run.name, "stage": stage, **st})


def done(run_id: str, stage: str, note: str | None = None, skip_validate: bool = False):
    from .validate import validate_stage
    run = run_dir(run_id)
    if not skip_validate:
        problems = validate_stage(stage, run)
        if problems:
            set_stage(run, stage, state="invalid", problems=problems[:30])
            die(f"{stage} output fails its contract", problems=problems[:30])
    m = load(run)
    retries = m["stages"].get(stage, {}).get("retries", 0)
    st = set_stage(run, stage, state="done", ended=now(), note=note, problems=[], retries=retries)
    out({"run": run.name, "stage": stage, **st})


def fail(run_id: str, stage: str, reason: str):
    run = run_dir(run_id)
    st = set_stage(run, stage, state="failed", ended=now(), note=reason)
    out({"run": run.name, "stage": stage, **st})


def gate(run_id: str, name: str, approve: bool, by: str | None, note: str | None, override: str | None):
    from . import pipelines
    run = run_dir(run_id)
    names = pipelines.gates(pipelines.of_run(run))
    if name not in names:
        die(f"unknown gate {name}; this run's pipeline has gates {names}")
    with locked(run):
        m = load(run)
        g = m["gates"].setdefault(name, _gate())
        if override:
            g["overrides"].append({"text": override, "by": by, "at": now()})
        if approve:
            if not by:
                die("an approval needs --by <editor name>")
            g.update(approved=True, by=by, at=now(), note=note)
        write_json(run / "run.json", m)
    out({"run": run.name, "gate": name, **g})


def approve_gate(run: Path, name: str, by: str, note: str | None = None) -> dict:
    """Open a gate without printing: the driver's automatic approvals (config/editorial.yaml → gates.auto)."""
    with locked(run):
        m = load(run)
        g = m["gates"].setdefault(name, _gate())
        g.update(approved=True, by=by, at=now(), note=note)
        write_json(run / "run.json", m)
    return g


def status(run_id: str | None):
    if not run_id:
        runs = sorted(p.name for p in RUNS.iterdir() if (p / "run.json").exists()) if RUNS.exists() else []
        out({"runs": runs})
        return
    m = load(run_dir(run_id))
    out(m)
