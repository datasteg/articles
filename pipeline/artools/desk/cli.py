"""`artools desk …`: the data desk's commands."""
from __future__ import annotations

from ..paths import RUNS, die, out, read_json, run_dir


def main(a) -> None:
    c = a.cmd
    if c == "watch":
        from . import watch
        from .api import Api
        snap = watch.snapshot(Api())
        out({"changed": watch.changes(snap, watch.load()), "apps": snap["apps"], "periods": snap["periods"]})
    elif c == "leads":
        from . import leads, panel, watch
        from .api import Api
        api = Api(offline=a.offline)
        changed = [] if a.offline else watch.changes(watch.snapshot(api), watch.load())
        found = leads.find(panel.build(api), api, changed)
        out([{k: l.get(k) for k in ("key", "screen", "score", "fresh", "covered_recently", "claim", "error") if l.get(k)} for l in found])
    elif c == "note":
        from . import run
        out(run.note(a.id, offline=a.offline, lead_key=a.lead, max_rounds=a.rounds, rewrite_of=a.rewrite_of, rewrite_why=a.why, idea=a.idea))
    elif c == "replay":
        from . import replay
        out(replay.replay(a.run, against=a.against, model=not a.no_model))
    elif c == "compare":
        from pathlib import Path
        from . import replay
        out(replay.compare(a.old, a.new, read_json(Path(a.replay)) if a.replay else None))
    elif c == "daily":
        from . import queue
        out(queue.daily(force=a.force, deploy=not a.no_deploy))
    elif c == "status":
        if a.run:
            r = run_dir(a.run)
            out({"result": read_json(r / "desk" / "result.json"), "score": read_json(r / "desk" / "score.json")})
        else:
            rows = [read_json(p) for p in sorted(RUNS.glob("*/desk/result.json"))]
            out([{k: r.get(k) for k in ("run", "status", "title", "lead", "score", "bar", "cost_usd", "words")} for r in rows if r])
    elif c == "show":
        from . import facts, tables, text   # noqa: F401
        r = run_dir(a.run)
        draft = read_json(r / "draft" / "en.json")
        if not draft:
            die("no draft in this run")
        fmap = {f["id"]: f for f in facts.load(r)}
        charts = {p.stem: read_json(p) for p in sorted((r / "charts").glob("*.json"))}
        print(text.article(draft, fmap, charts, a.view))
    elif c == "calibrate":
        from . import judge
        out(judge.calibrate(a.n, a.only)["summary"])
    elif c == "rejudge":
        from . import config, judge
        r = run_dir(a.run)
        s = judge.score_text(r, (r / "desk" / "judged.txt").read_text(encoding="utf-8"), a.n)   # --n 1: one judge, as notes are scored since R7
        out({"score": s, "bar": judge.bar(config.load())})
    elif c == "korean":
        from . import korean, queue
        r = run_dir(a.run)
        ko = korean.make(r, redo=a.redo)
        from . import claims as claims_mod, facts as facts_mod, run as run_mod
        if ko.get("written") and claims_mod.load(r):        # the refined pipeline: the inference test on the Korean surface (R4, R8)
            ko = run_mod.korean_inference(r, facts_mod.load(r), claims_mod.load(r)) or ko
        queue.proof_pdf(r)
        out({"korean": {k: ko.get(k) for k in ("complete", "written", "flagged", "error")} | {"open": len(ko.get("open") or [])}, **queue.settle(r)})
    elif c == "ideas":
        from . import ideas
        out(ideas.make(force=a.force))
    elif c == "queue":
        from . import queue
        out(queue.export(deploy=a.deploy))
    elif c == "sync":
        from . import queue
        out(queue.sync(dry_run=a.dry_run))
    elif c == "withdraw":
        from . import queue
        out(queue.withdraw(a.run, a.why))
    elif c == "update":
        from . import queue
        pts = [{"id": k.strip(), "problem": v.strip()} for k, v in (x.split(":", 1) for x in a.ko or [] if ":" in x)]
        out(queue.update(a.run, a.note, a.correction, [x.strip() for x in (a.only or "").split(",") if x.strip()] or None, pts or None))
    elif c == "decide":
        from . import queue
        out(queue.decide_local(a.run, a.decision, a.by, a.note, a.title_ko))
